"""Endpoints de configuração do LLM — troca de provider/modelo/chave em RUNTIME.

A chave de API entra por aqui e fica só em memória no servidor; nunca é
retornada por GET nem registrada em log.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_config
from app.llm import provider

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    api_key: str | None = None
    mock: bool | None = None
    usd_brl_rate: float | None = None


@router.get("")
def get_settings() -> dict:
    return get_config().public_snapshot()


@router.put("")
def update_settings(body: SettingsUpdate) -> dict:
    cfg = get_config()
    cfg.update(
        provider=body.provider,
        model=body.model,
        temperature=body.temperature,
        api_key=body.api_key,
        mock=body.mock,
        usd_brl_rate=body.usd_brl_rate,
    )
    return cfg.public_snapshot()


@router.post("/test")
def test_settings() -> dict:
    """Valida o provider/modelo/chave atuais com uma chamada barata."""
    cfg = get_config()
    if cfg.mock:
        return {"ok": True, "mock": True, "message": "Modo mock ativo (sem chamada real)."}
    if not cfg.active_key():
        return {"ok": False, "message": f"Sem chave de API para o provider '{cfg.provider}'."}
    try:
        provider.ping()
        return {"ok": True, "message": f"Conexão OK com {cfg.provider} / {cfg.model}."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": str(e)}
