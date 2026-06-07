"""Medição de uso (tokens + custo) — acumulação no provider e meta.usage."""

from __future__ import annotations

import types


class _Resp(dict):
    """Resposta fake do litellm: dict (p/ resp['choices']) + atributo .usage."""


def _fake_resp(pt: int = 10, ct: int = 5) -> _Resp:
    r = _Resp(choices=[{"message": {"content": "ok"}}])
    r.usage = types.SimpleNamespace(prompt_tokens=pt, completion_tokens=ct, total_tokens=pt + ct)
    return r


def test_usage_meter_acumula_tokens_e_custo(monkeypatch):
    from app.llm import provider

    monkeypatch.setattr(provider.litellm, "completion", lambda **kw: _fake_resp(10, 5))
    monkeypatch.setattr(provider.litellm, "completion_cost", lambda completion_response=None: 0.0002)

    with provider.meter() as m:
        provider.chat([{"role": "user", "content": "a"}])
        provider.chat([{"role": "user", "content": "b"}])
    snap = m.snapshot()

    assert snap["calls"] == 2
    assert snap["prompt_tokens"] == 20
    assert snap["completion_tokens"] == 10
    assert snap["total_tokens"] == 30
    assert snap["cost_known"] is True
    assert round(snap["cost_usd"], 4) == 0.0004


def test_usage_sem_escopo_nao_quebra(monkeypatch):
    from app.llm import provider

    monkeypatch.setattr(provider.litellm, "completion", lambda **kw: _fake_resp())
    monkeypatch.setattr(provider.litellm, "completion_cost", lambda completion_response=None: 0.0)
    # Sem `meter()` ativo, current_usage é None e a chamada não quebra.
    assert provider.current_usage() is None
    assert provider.chat([{"role": "user", "content": "a"}]) == "ok"


def test_custo_desconhecido_marca_cost_known_false(monkeypatch):
    from app.llm import provider

    def _boom(completion_response=None):
        raise RuntimeError("modelo sem preço na tabela")

    monkeypatch.setattr(provider.litellm, "completion", lambda **kw: _fake_resp(7, 3))
    monkeypatch.setattr(provider.litellm, "completion_cost", _boom)

    with provider.meter() as m:
        provider.chat([{"role": "user", "content": "a"}])
    snap = m.snapshot()
    assert snap["total_tokens"] == 10
    assert snap["cost_known"] is False
    assert snap["cost_usd"] == 0.0


def test_ciclope_mock_tem_meta_usage():
    from app.ciclope import pipeline

    tm = pipeline.analyze(b"fake-image-bytes")
    usage = tm.meta.get("usage")
    assert usage is not None
    assert usage["mock"] is True
    assert usage["total_tokens"] == 0
