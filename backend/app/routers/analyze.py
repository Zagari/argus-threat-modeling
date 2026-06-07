from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import cast

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.argus import detect as detector
from app.argus import orchestrator
from app.ciclope import pipeline as ciclope
from app.llm import provider
from app.schemas import ThreatModel

router = APIRouter(tags=["analyze"])


@router.post("/analyze", response_model=ThreatModel)
async def analyze(
    file: UploadFile = File(...),
    system: str = Query("ciclope", description="ciclope | argus"),
    system_name: str | None = Query(None),
) -> ThreatModel:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Arquivo de imagem vazio.")
    mime = file.content_type or "image/jpeg"

    if system == "ciclope":
        try:
            return ciclope.analyze(data, system_name=system_name, mime=mime)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=str(e)) from e
    if system == "argus":
        try:
            return orchestrator.run(data, system_name=system_name)
        except detector.DetectorUnavailable as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=str(e)) from e
    raise HTTPException(status_code=400, detail=f"system inválido: {system}")


# ── Streaming (SSE): um evento por estágio do pipeline ───────────────────────
def _sse(event: str, data: dict) -> bytes:
    """Serializa um quadro SSE. Pydantic vira dict via `model_dump` (default)."""
    def _default(o: object) -> object:
        if isinstance(o, BaseModel):
            return o.model_dump()
        return str(o)

    payload = json.dumps(data, ensure_ascii=False, default=_default)
    return f"event: {event}\ndata: {payload}\n\n".encode()


@router.post("/analyze/stream")
async def analyze_stream(
    file: UploadFile = File(...),
    system: str = Query("argus", description="ciclope | argus"),
    system_name: str | None = Query(None),
) -> StreamingResponse:
    """Roda a análise emitindo eventos por estágio (text/event-stream).

    `argus` emite a esteira completa (E1→E4); `ciclope` emite ``start`` e ``done`` (uma única
    passagem do VLM). Erros viram um evento ``error`` (com ``status`` 503/502) em vez de derrubar
    a conexão. Lido no cliente via `fetch` + ReadableStream (POST aceita o upload do diagrama).
    """
    data = await file.read()
    mime = file.content_type or "image/jpeg"
    if not data:
        raise HTTPException(status_code=400, detail="Arquivo de imagem vazio.")

    async def gen() -> AsyncIterator[bytes]:
        try:
            if system == "ciclope":
                yield _sse("start", {"system": "ciclope", "system_name": system_name or "Sistema sob análise"})
                tm = await run_in_threadpool(ciclope.analyze, data, system_name=system_name, mime=mime)
                yield _sse("done", {"threat_model": tm})
            elif system == "argus":
                # Escopo de medição no contexto async: o threadpool copia o contexto a cada
                # `next()`, então o medidor (objeto mutável) é compartilhado entre os estágios.
                with provider.meter():
                    it = orchestrator.iter_stages(data, system_name=system_name)
                    sentinel = object()
                    while True:
                        result = await run_in_threadpool(next, it, sentinel)
                        if result is sentinel:
                            break
                        ev = cast(dict, result)
                        stage = ev.pop("stage")
                        yield _sse(stage, ev)
            else:
                yield _sse("error", {"status": 400, "message": f"system inválido: {system}"})
        except detector.DetectorUnavailable as e:
            yield _sse("error", {"status": 503, "message": str(e)})
        except Exception as e:  # noqa: BLE001
            yield _sse("error", {"status": 502, "message": str(e)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
