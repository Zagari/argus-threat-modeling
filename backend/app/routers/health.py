from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.argus import detect as detector
from app.argus.knowledge import rag
from app.config import get_config

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/capabilities")
def capabilities() -> dict:
    """Capacidades do ambiente: se o ARGUS (pipeline E1–E4) está disponível e o LLM atual.

    `argus_ml` é a chave que a UI usa para habilitar a aba/análise do ARGUS. É um teste
    BARATO (env + deps), sem baixar pesos nem importar torch — o detector só carrega de fato
    na primeira análise.
    """
    cfg = get_config()
    return {
        "version": __version__,
        "argus_ml": detector.configured(),
        "llm": {"provider": cfg.provider, "model": cfg.model, "mock": cfg.mock},
        "usd_brl_rate": cfg.usd_brl_rate,
        "cost_factor": cfg.cost_factor,
        "rag": rag.status(),
    }
