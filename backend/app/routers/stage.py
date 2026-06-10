"""Inspetor do pipeline ARGUS, estágio a estágio.

E1 (detecção) e E2 (OCR + fusão ícone/rótulo + topologia via VLM). Cada estágio tem
endpoint próprio para a UI mostrar resultados parciais.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.argus import crosscheck, dfd, fusion, ocr, topology
from app.argus import detect as detector
from app.schemas import DetectionResult, TextRegion, TopologyResult

router = APIRouter(prefix="/stage", tags=["stage"])


# ── E1: detecção ────────────────────────────────────────────────────────────
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


# ── E2a: OCR ────────────────────────────────────────────────────────────────
@router.get("/ocr/status")
def ocr_status() -> dict:
    """Diz se há um motor de OCR disponível (PaddleOCR/EasyOCR)."""
    return ocr.status()


@router.post("/ocr", response_model=list[TextRegion])
async def stage_ocr(file: UploadFile = File(...)) -> list[TextRegion]:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Arquivo de imagem vazio.")
    try:
        return ocr.read_text(data)
    except ocr.OcrUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Falha no OCR: {e}") from e


# ── E1→E2: pipeline compartilhada (detecção + OCR/fusão + cross-check + topologia) ──
def _run_e1_e2(data: bytes, conf: float | None) -> dict:
    """Roda E1→E2 e devolve componentes (fundidos/checados), arestas e metadados."""
    if not data:
        raise HTTPException(status_code=400, detail="Arquivo de imagem vazio.")

    # E1 — detecção (obrigatória)
    try:
        det = detector.detect(data, conf=conf)
    except detector.DetectorUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Falha na detecção: {e}") from e
    components = det["components"]

    # E2a — OCR + fusão (opcional: se não houver OCR, segue sem rótulos)
    text_regions: list[TextRegion] = []
    ocr_used = False
    if ocr.available():
        try:
            text_regions = ocr.read_text(data)
            components = fusion.fuse(components, text_regions)
            ocr_used = True
        except Exception:  # noqa: BLE001 — OCR é um reforço; não derruba o estágio
            text_regions = []

    # E2 — cross-check de classificação via VLM (corrige incertos + propõe faltantes)
    crosscheck_used = False
    if os.getenv("ARGUS_CROSSCHECK", "1") == "1":
        try:
            components = crosscheck.verify(data, components)
            crosscheck_used = True
        except Exception:  # noqa: BLE001 — cross-check é reforço; não derruba o estágio
            crosscheck_used = False

    # E2b — topologia (VLM)
    try:
        edges, _ = topology.extract(data, components)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Falha na topologia: {e}") from e

    return {
        "components": components, "edges": edges, "text_regions": text_regions,
        "annotated_image": det.get("annotated_image"),
        "meta": {"detections": len(components), "edges": len(edges),
                 "ocr_used": ocr_used, "crosscheck_used": crosscheck_used},
    }


@router.post("/topology", response_model=TopologyResult)
async def stage_topology(
    file: UploadFile = File(...),
    conf: float | None = Query(None, ge=0.0, le=1.0),
) -> TopologyResult:
    """E1→E2: detecta, funde rótulos do OCR, cross-check (VLM) e extrai a topologia (VLM)."""
    r = _run_e1_e2(await file.read(), conf)
    return TopologyResult(**r)


# ── E3: DFD (tipagem do grafo + fronteiras de confiança) ─────────────────────
@router.post("/dfd", response_model=TopologyResult)
async def stage_dfd(
    file: UploadFile = File(...),
    conf: float | None = Query(None, ge=0.0, le=1.0),
) -> TopologyResult:
    """E1→E3: além do E2, marca os fluxos que cruzam fronteiras de confiança (DFD)."""
    r = _run_e1_e2(await file.read(), conf)
    edges = dfd.mark_crossings(r["components"], r["edges"])
    r["meta"] |= dfd.summarize(r["components"], edges)
    return TopologyResult(components=r["components"], edges=edges,
                          text_regions=r["text_regions"],
                          annotated_image=r["annotated_image"], meta=r["meta"])
