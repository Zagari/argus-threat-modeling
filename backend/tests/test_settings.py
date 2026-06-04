"""Troca de provider em runtime + garantia de que a chave nunca vaza."""

from __future__ import annotations


def test_get_settings_nao_expoe_chave(client):
    r = client.get("/settings")
    assert r.status_code == 200
    body = r.json()
    assert "api_key" not in body
    assert isinstance(body["has_key"], bool)
    assert "available_providers" in body


def test_troca_provider_em_runtime_sem_vazar_chave(client):
    r = client.put("/settings", json={"provider": "openai", "api_key": "sk-segredo-123"})
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "openai"
    assert body["model"] == "openai/gpt-4o"  # default ao trocar de provider
    assert body["has_key"] is True
    assert "openai" in body["providers_with_key"]
    # a chave NÃO pode aparecer em lugar nenhum da resposta
    assert "sk-segredo-123" not in r.text


def test_settings_test_em_modo_mock(client):
    r = client.post("/settings/test")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body.get("mock") is True
