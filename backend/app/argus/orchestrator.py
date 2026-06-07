"""Orquestrador do ARGUS — roda o pipeline E1→E4 e monta o `ThreatModel`.

É o equivalente especialista do Cíclope: mesma saída (`ThreatModel`), mas construída pela
esteira detector → OCR/fusão → cross-check (VLM) → topologia (VLM) → DFD → STRIDE-per-element.
Levanta `detect.DetectorUnavailable` quando o detector não está disponível (o router converte
em 503); o caminho VLM (cross-check/topologia/STRIDE) roda em qualquer ambiente com chave.
"""

from __future__ import annotations

import os
import time

from app.argus import crosscheck, dfd, fusion, ocr, stride, topology
from app.argus import detect as detector
from app.config import get_config
from app.schemas import ThreatModel


def run(image_bytes: bytes, *, conf: float | None = None, system_name: str | None = None) -> ThreatModel:
    t0 = time.perf_counter()

    # E1 — detecção (obrigatória; lança DetectorUnavailable)
    components = detector.detect(image_bytes, conf=conf)["components"]

    # E2a — OCR + fusão (reforço opcional)
    ocr_used = False
    if ocr.available():
        try:
            components = fusion.fuse(components, ocr.read_text(image_bytes))
            ocr_used = True
        except Exception:  # noqa: BLE001
            ocr_used = False

    # E2 — cross-check + completude (VLM)
    if os.getenv("ARGUS_CROSSCHECK", "1") == "1":
        try:
            components = crosscheck.verify(image_bytes, components)
        except Exception:  # noqa: BLE001
            pass

    # E2b — topologia (VLM) · E3 — DFD (fronteiras) · E4 — STRIDE-per-element
    edges = dfd.mark_crossings(components, topology.extract(image_bytes, components))
    threats = stride.generate(components, edges)

    cfg = get_config()
    latency = round(time.perf_counter() - t0, 3)
    return ThreatModel(
        system_name=system_name or "Sistema sob análise",
        components=components,
        edges=edges,
        threats=threats,
        meta={
            "system": "argus", "provider": cfg.provider, "model": cfg.model,
            "latency_s": latency, "ocr_used": ocr_used, "threats": len(threats),
            **dfd.summarize(components, edges),
        },
    )
