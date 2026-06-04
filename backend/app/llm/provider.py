"""Camada de abstração de LLM via litellm — chat e visão, com structured output.

Um único ponto de chamada para qualquer provider (Gemini/Anthropic/OpenAI),
trocável em runtime (ver app.config). Suporta `response_model` (Pydantic):
instrui JSON pelo schema, parseia, valida e re-tenta uma vez em caso de falha.
"""

from __future__ import annotations

import base64
import json
from typing import TypeVar

import litellm
from pydantic import BaseModel, ValidationError

from app.config import get_config

litellm.drop_params = True  # ignora params não suportados por um dado provider

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


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
    }
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
        raise LLMError(f"Falha ao chamar o LLM ({cfg.provider} / {cfg.model}): {e}") from e

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
