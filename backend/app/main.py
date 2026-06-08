"""Entrypoint FastAPI — ARGUS & Cíclope (Fase 0)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_config
from app.routers import analyze, health, knowledge, report, settings, stage


def create_app() -> FastAPI:
    cfg = get_config()
    app = FastAPI(
        title="ARGUS & Cíclope API",
        version=__version__,
        description="Modelagem de ameaças STRIDE a partir de diagramas de arquitetura.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins or ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )
    app.include_router(health.router)
    app.include_router(settings.router)
    app.include_router(analyze.router)
    app.include_router(report.router)
    app.include_router(stage.router)
    app.include_router(knowledge.router)
    return app


app = create_app()
