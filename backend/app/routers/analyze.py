from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.argus import detect as detector
from app.argus import orchestrator
from app.ciclope import pipeline as ciclope
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
