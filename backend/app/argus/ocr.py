"""E2 — OCR plugável (PaddleOCR primário, EasyOCR fallback).

Lê os rótulos de texto do diagrama → `list[TextRegion]` (texto + bbox normalizado + conf).
Como as deps de OCR são pesadas e específicas de ambiente de ML, os imports são
**preguiçosos** e o módulo importa sem erro mesmo sem elas; sem motor disponível,
levanta `OcrUnavailable` (o router converte em 503).

Configuração por ambiente:
  ARGUS_OCR_ENGINE  auto (default) | paddle | easyocr
  ARGUS_OCR_GPU     1 para forçar GPU (default: autodetecta CUDA via torch)
  ARGUS_OCR_LANGS   idiomas do EasyOCR (default: "en,pt")
"""

from __future__ import annotations

import io
import os
import threading
from typing import Any

from app.schemas import TextRegion

_reader: Any = None
_engine: str = ""
_lock = threading.Lock()


class OcrUnavailable(RuntimeError):
    """Nenhum motor de OCR instalado/utilizável neste ambiente."""


def _use_gpu() -> bool:
    env = os.getenv("ARGUS_OCR_GPU")
    if env is not None:
        return env == "1"
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return False


def _load() -> tuple[Any, str]:
    global _reader, _engine
    if _reader is not None:
        return _reader, _engine
    with _lock:
        if _reader is not None:
            return _reader, _engine
        pref = os.getenv("ARGUS_OCR_ENGINE", "auto").lower()
        order = {"auto": ["paddle", "easyocr"]}.get(pref, [pref])
        errors: list[str] = []
        for eng in order:
            try:
                if eng == "paddle":
                    from paddleocr import PaddleOCR

                    _reader = PaddleOCR(use_angle_cls=False, lang="en", show_log=False)
                    _engine = "paddle"
                    return _reader, _engine
                if eng == "easyocr":
                    import easyocr

                    langs = [s.strip() for s in os.getenv("ARGUS_OCR_LANGS", "en,pt").split(",") if s.strip()]
                    _reader = easyocr.Reader(langs, gpu=_use_gpu())
                    _engine = "easyocr"
                    return _reader, _engine
            except Exception as e:  # noqa: BLE001 — tenta o próximo motor
                errors.append(f"{eng}: {type(e).__name__}: {e}")
        raise OcrUnavailable(
            "Nenhum motor de OCR disponível. Instale `easyocr` (ou `paddleocr`) no ambiente "
            "de ML (ver backend/requirements-ml.txt). Detalhes: " + " | ".join(errors)
        )


def available() -> bool:
    try:
        _load()
        return True
    except OcrUnavailable:
        return False


def status() -> dict:
    try:
        _load()
        return {"available": True, "engine": _engine}
    except OcrUnavailable as e:
        return {"available": False, "reason": str(e)}


def _bbox_from_points(points: list, width: int, height: int) -> list[float]:
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
    return [round(x1 / width, 5), round(y1 / height, 5),
            round((x2 - x1) / width, 5), round((y2 - y1) / height, 5)]


def read_text(image_bytes: bytes) -> list[TextRegion]:
    """Roda o OCR e retorna as regiões de texto com caixa normalizada [x,y,w,h]."""
    reader, engine = _load()
    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = img.size
    arr = np.array(img)
    regions: list[TextRegion] = []

    if engine == "easyocr":
        for box, text, conf in reader.readtext(arr):
            if str(text).strip():
                regions.append(TextRegion(text=str(text).strip(),
                                          bbox=_bbox_from_points(box, width, height),
                                          confidence=round(float(conf), 4)))
    elif engine == "paddle":
        result = reader.ocr(arr, cls=False)
        for line in (result[0] if result else []) or []:
            box, (text, conf) = line[0], line[1]
            if str(text).strip():
                regions.append(TextRegion(text=str(text).strip(),
                                          bbox=_bbox_from_points(box, width, height),
                                          confidence=round(float(conf), 4)))
    return regions
