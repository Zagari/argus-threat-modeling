"""Entrypoint FastAPI — ARGUS & Cíclope (Fase 0)."""

from __future__ import annotations

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.argus.knowledge import rag
from app.config import get_config
from app.routers import analyze, compare, health, knowledge, report, settings, stage


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Aquece o índice semântico (Chroma) em BACKGROUND: o app fica disponível na hora; o
    # índice constrói/carrega numa thread e o RAG "liga" quando pronto (até lá, fallback).
    if rag.enabled():
        threading.Thread(target=rag.warm, name="rag-warm", daemon=True).start()
    yield


def create_app() -> FastAPI:
    cfg = get_config()
    app = FastAPI(
        title="ARGUS & Cíclope API",
        version=__version__,
        description="Modelagem de ameaças STRIDE a partir de diagramas de arquitetura.",
        lifespan=_lifespan,
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
    app.include_router(compare.router)
    return app


app = create_app()
