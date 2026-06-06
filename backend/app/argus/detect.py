"""E1 — Detecção de componentes no diagrama (YOLO11).

Carrega o detector treinado (`best.pt`) e roda inferência sobre a imagem,
devolvendo `Component`s canônicos com bbox e confiança + uma imagem anotada.

As dependências de ML (ultralytics/torch) são pesadas e NÃO fazem parte do
backend de produção (Python 3.14, sem torch). Por isso todos os imports pesados
são **preguiçosos**: este módulo importa sem erro mesmo sem torch, e a detecção
só é tentada quando chamada. Sem o modelo/deps, levanta `DetectorUnavailable`
(o router converte em HTTP 503 com mensagem clara).

Configuração por ambiente:
  ARGUS_DETECTOR_WEIGHTS  caminho local do best.pt
  ARGUS_DETECTOR_HF       repo do HF Hub (ex.: "Zagari/argus-detector") — baixa best.pt
  ARGUS_DETECTOR_FILE     nome do arquivo no repo HF (default: best.pt)
  ARGUS_DETECTOR_CONF     confiança mínima (default 0.25)
  ARGUS_DETECTOR_IMGSZ    tamanho de inferência (default 1280)
"""

from __future__ import annotations

import base64
import io
import os
import threading
from pathlib import Path
from typing import Any

from app.schemas import Component
from app.taxonomy import CANONICAL_ELEMENT_TYPE

_model: Any = None
_weights_label: str = ""
_lock = threading.Lock()


class DetectorUnavailable(RuntimeError):
    """Detector não configurado ou deps de ML ausentes neste ambiente."""


def _resolve_weights() -> str | None:
    """Caminho local do best.pt: env explícito ou download do HF Hub."""
    local = os.getenv("ARGUS_DETECTOR_WEIGHTS")
    if local:
        if not Path(local).exists():
            raise DetectorUnavailable(f"ARGUS_DETECTOR_WEIGHTS aponta p/ arquivo inexistente: {local}")
        return local
    repo = os.getenv("ARGUS_DETECTOR_HF")
    if repo:
        try:
            from huggingface_hub import hf_hub_download
        except ImportError as e:
            raise DetectorUnavailable("huggingface_hub não instalado (pip install huggingface_hub).") from e
        return hf_hub_download(repo_id=repo, filename=os.getenv("ARGUS_DETECTOR_FILE", "best.pt"))
    return None


def _load() -> Any:
    global _model, _weights_label
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        weights = _resolve_weights()
        if not weights:
            raise DetectorUnavailable(
                "Detector E1 não configurado. Defina ARGUS_DETECTOR_WEIGHTS (caminho do best.pt) "
                "ou ARGUS_DETECTOR_HF (repo do HF Hub)."
            )
        try:
            from ultralytics import YOLO
        except ImportError as e:
            raise DetectorUnavailable(
                "ultralytics/torch não instalados neste ambiente. Para usar o E1, rode o backend "
                "num ambiente com as deps de ML (ver backend/requirements-ml.txt; Python 3.12)."
            ) from e
        _model = YOLO(weights)
        _weights_label = Path(weights).name
    return _model


def available() -> bool:
    """True se o detector pode ser carregado (deps + pesos presentes)."""
    try:
        _load()
        return True
    except DetectorUnavailable:
        return False


def status() -> dict:
    try:
        _load()
        return {"available": True, "weights": _weights_label}
    except DetectorUnavailable as e:
        return {"available": False, "reason": str(e)}


def detect(image_bytes: bytes, *, conf: float | None = None, imgsz: int | None = None) -> dict:
    """Roda o detector → componentes (bbox normalizado [x,y,w,h]) + imagem anotada."""
    model = _load()
    from PIL import Image

    conf = conf if conf is not None else float(os.getenv("ARGUS_DETECTOR_CONF", "0.25"))
    imgsz = imgsz if imgsz is not None else int(os.getenv("ARGUS_DETECTOR_IMGSZ", "1280"))

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = img.size
    results = model.predict(source=img, conf=conf, imgsz=imgsz, verbose=False)
    r = results[0]
    names = r.names  # {idx: yolo_name}

    boxes = r.boxes
    xyxy = boxes.xyxy.cpu().numpy()
    confs = boxes.conf.cpu().numpy()
    clss = boxes.cls.cpu().numpy().astype(int)

    components: list[Component] = []
    for i in range(len(xyxy)):
        x1, y1, x2, y2 = (float(v) for v in xyxy[i])
        name = names.get(int(clss[i]), str(int(clss[i])))
        bbox = [
            round(x1 / width, 5),
            round(y1 / height, 5),
            round((x2 - x1) / width, 5),
            round((y2 - y1) / height, 5),
        ]
        components.append(
            Component(
                id=f"C{i + 1}",
                canonical=name,
                label=name.replace("_", " "),
                element_type=CANONICAL_ELEMENT_TYPE.get(name, "Process"),  # type: ignore[arg-type]
                bbox=bbox,
                confidence=round(float(confs[i]), 4),
            )
        )

    annotated = _annotate(r)
    return {
        "components": components,
        "annotated_image": annotated,
        "model": {"weights": _weights_label, "detections": len(components), "conf": conf, "imgsz": imgsz},
    }


def _annotate(result: Any) -> str | None:
    """Imagem com as caixas desenhadas (data URL base64), via plot() do ultralytics."""
    try:
        import cv2

        bgr = result.plot()  # numpy BGR com boxes/labels
        ok, buf = cv2.imencode(".png", bgr)
        if not ok:
            return None
        return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")
    except Exception:  # noqa: BLE001 — anotação é um extra; nunca derruba a detecção
        return None
