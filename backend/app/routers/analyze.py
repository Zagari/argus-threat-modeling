from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

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
        raise HTTPException(status_code=501, detail="ARGUS será implementado a partir da Fase 2.")
    raise HTTPException(status_code=400, detail=f"system inválido: {system}")
