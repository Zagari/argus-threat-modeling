"""Inspetor do pipeline ARGUS, estágio a estágio. Começa pelo E1 (detecção).

Cada estágio ganha um endpoint próprio para a UI mostrar resultados parciais.
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.argus import detect as detector
from app.schemas import DetectionResult

router = APIRouter(prefix="/stage", tags=["stage"])


@router.get("/detect/status")
def detect_status() -> dict:
    """Diz se o detector E1 está disponível neste ambiente (deps + pesos)."""
    return detector.status()


@router.post("/detect", response_model=DetectionResult)
async def stage_detect(
    file: UploadFile = File(...),
    conf: float | None = Query(None, ge=0.0, le=1.0, description="confiança mínima"),
) -> DetectionResult:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Arquivo de imagem vazio.")
    try:
        result = detector.detect(data, conf=conf)
    except detector.DetectorUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Falha na detecção: {e}") from e
    return DetectionResult(**result)
