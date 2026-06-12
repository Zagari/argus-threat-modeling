"""Camada de abstração de LLM via litellm — chat e visão, com structured output.

Um único ponto de chamada para qualquer provider (Gemini/Anthropic/OpenAI),
trocável em runtime (ver app.config). Suporta `response_model` (Pydantic):
instrui JSON pelo schema, parseia, valida e re-tenta uma vez em caso de falha.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TypeVar

import litellm
from pydantic import BaseModel, ValidationError

from app.config import get_config

litellm.drop_params = True  # ignora params não suportados por um dado provider

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


# ── Medição de uso (tokens + custo) por requisição ───────────────────────────
@dataclass
class UsageMeter:
    """Acumula tokens e custo das chamadas de LLM dentro de um escopo (`meter()`).

    Os tokens vêm do provider (exatos; para visão, os tokens da imagem entram em
    `prompt_tokens`). O custo é a estimativa do litellm (`completion_cost`) — pode faltar
    para algum modelo, daí `cost_known=False`. Acumula as N chamadas do ARGUS (cross-check,
    topologia, STRIDE) ou a única do Cíclope.
    """

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    cost_known: bool = False

    def add(self, *, prompt: int, completion: int, total: int, cost: float, cost_known: bool) -> None:
        self.calls += 1
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += total
        self.cost_usd += cost
        self.cost_known = self.cost_known or cost_known

    def snapshot(self) -> dict:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "cost_known": self.cost_known,
        }


_meter: ContextVar[UsageMeter | None] = ContextVar("argus_llm_meter", default=None)


@contextmanager
def meter() -> Iterator[UsageMeter]:
    """Escopo de medição. Reentrante: se já houver um medidor ativo, reusa (não aninha)."""
    existing = _meter.get()
    if existing is not None:
        yield existing
        return
    m = UsageMeter()
    token = _meter.set(m)
    try:
        yield m
    finally:
        _meter.reset(token)


def current_usage() -> dict | None:
    """Snapshot do medidor ativo (ou None se não houver escopo `meter()`)."""
    m = _meter.get()
    return m.snapshot() if m is not None else None


def _u(usage: object, key: str) -> int:
    if usage is None:
        return 0
    if isinstance(usage, dict):
        return int(usage.get(key) or 0)
    return int(getattr(usage, key, 0) or 0)


def _record_usage(resp: object) -> None:
    """Lê tokens (provider) + custo (litellm) da resposta e soma no medidor ativo."""
    m = _meter.get()
    if m is None:
        return
    usage = getattr(resp, "usage", None)
    if usage is None and hasattr(resp, "get"):
        usage = resp.get("usage")  # type: ignore[attr-defined]
    pt, ct = _u(usage, "prompt_tokens"), _u(usage, "completion_tokens")
    tt = _u(usage, "total_tokens") or (pt + ct)
    cost, cost_known = 0.0, False
    try:
        c = litellm.completion_cost(completion_response=resp)
        if c is not None:
            cost, cost_known = float(c), True
    except Exception:  # noqa: BLE001 — custo é estimativa; nunca derruba a chamada
        cost, cost_known = 0.0, False
    m.add(prompt=pt, completion=ct, total=tt, cost=cost, cost_known=cost_known)


def _extract_text(resp) -> str:
    try:
        return resp["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:  # pragma: no cover
        raise LLMError(f"Resposta do LLM em formato inesperado: {e}") from e


def _append_to_last_user(messages: list[dict], extra: str) -> list[dict]:
    msgs = [dict(m) for m in messages]
    for m in reversed(msgs):
        if m.get("role") == "user":
            content = m["content"]
            if isinstance(content, list):
                m["content"] = content + [{"type": "text", "text": extra}]
            else:
                m["content"] = (content or "") + extra
            return msgs
    msgs.append({"role": "user", "content": extra})
    return msgs


def _parse_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if "\n" in t:
            t = t.split("\n", 1)[1]
    i, j = t.find("{"), t.rfind("}")
    if i == -1 or j == -1:
        raise ValueError("nenhum objeto JSON encontrado na resposta")
    return json.loads(t[i : j + 1])


def _completion_kwargs(temperature: float | None) -> dict:
    cfg = get_config()
    kw: dict = {
        "model": cfg.model,
        "temperature": cfg.temperature if temperature is None else temperature,
        "timeout": cfg.timeout,   # falha limpa em vez de pendurar (ver config)
    }
    if cfg.provider == "gemini":
        # Desliga o "thinking" do Gemini (litellm -> thinkingConfig.thinkingBudget=0).
        # Sem isso, a análise de visão leva ~80s; com isso, ~3s. Ver config.timeout.
        kw["reasoning_effort"] = "disable"
    key = cfg.active_key()
    if key:
        kw["api_key"] = key
    return kw


def _complete(
    messages: list[dict],
    *,
    response_model: type[T] | None = None,
    temperature: float | None = None,
    _retry: bool = True,
) -> T | str:
    kw = _completion_kwargs(temperature)
    msgs = messages
    if response_model is not None:
        schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        instr = (
            "\n\nResponda ESTRITAMENTE com UM ÚNICO objeto JSON válido que satisfaça "
            f"este JSON Schema (sem markdown, sem comentários, sem texto fora do JSON):\n{schema}"
        )
        msgs = _append_to_last_user(msgs, instr)
        kw["response_format"] = {"type": "json_object"}

    try:
        resp = litellm.completion(messages=msgs, **kw)
    except Exception as e:  # noqa: BLE001 — normaliza qualquer erro de provider
        cfg = get_config()
        # Limite de taxa (429): comum após uma rajada de chamadas (ex.: rodar várias análises
        # seguidas). Mensagem clara em vez de um erro genérico que parece "travamento".
        if "RateLimit" in type(e).__name__ or "429" in str(e):
            raise LLMError(
                f"Limite de taxa do provedor ({cfg.provider}/{cfg.model}). "
                "Aguarde alguns segundos e rode novamente."
            ) from e
        raise LLMError(f"Falha ao chamar o LLM ({cfg.provider} / {cfg.model}): {e}") from e

    _record_usage(resp)
    text = _extract_text(resp)
    if response_model is None:
        return text

    try:
        return response_model.model_validate(_parse_json(text))
    except (ValueError, ValidationError) as e:
        if _retry:
            fix = (
                f"\n\nSua resposta anterior NÃO validou contra o schema ({e}). "
                "Corrija e responda apenas com o JSON válido."
            )
            return _complete(
                _append_to_last_user(msgs, fix),
                response_model=response_model,
                temperature=0.0,
                _retry=False,
            )
        raise LLMError(f"Saída do LLM não validou contra o schema: {e}") from e


def chat(
    messages: list[dict],
    *,
    response_model: type[T] | None = None,
    temperature: float | None = None,
) -> T | str:
    """Chamada texto→texto (ou texto→objeto validado, se response_model)."""
    return _complete(messages, response_model=response_model, temperature=temperature)


def vision(
    image_bytes: bytes,
    prompt: str,
    *,
    response_model: type[T] | None = None,
    mime: str = "image/jpeg",
    temperature: float | None = None,
    system: str | None = None,
) -> T | str:
    """Chamada imagem+texto → texto (ou objeto validado)."""
    data_uri = f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        }
    )
    return _complete(messages, response_model=response_model, temperature=temperature)


def ping() -> str:
    """Chamada barata para validar provider/modelo/chave (usada por /settings/test)."""
    return _complete([{"role": "user", "content": "ping"}], temperature=0.0)  # type: ignore[return-value]
