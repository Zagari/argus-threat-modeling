"""Orquestrador do ARGUS — roda o pipeline E1→E4 e monta o `ThreatModel`.

É o equivalente especialista do Cíclope: mesma saída (`ThreatModel`), mas construída pela
esteira detector → OCR/fusão → cross-check (VLM) → topologia (VLM) → DFD → STRIDE-per-element.

A orquestração é exposta como um GERADOR (`iter_stages`) que emite um evento por estágio —
é isso que alimenta o streaming SSE da UI (cards por estágio, com revelação progressiva).
`run()` apenas consome o gerador e devolve o `ThreatModel` final (caminho não-streaming).
Levanta `detect.DetectorUnavailable` quando o detector não está disponível (o router converte
em 503/evento de erro); o caminho VLM (cross-check/topologia/STRIDE) roda em qualquer ambiente
com chave.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator

from app.argus import crosscheck, dfd, fusion, ocr, scoring, stride, topology
from app.argus import detect as detector
from app.argus.knowledge import cve as kg_cve
from app.argus.knowledge import enrich
from app.argus.knowledge.store import get_store
from app.config import get_config
from app.llm import provider
from app.schemas import ThreatModel


def _usage_delta(before: dict | None, after: dict | None) -> dict | None:
    """Diferença de uso (tokens + custo) entre dois snapshots — o consumo do estágio."""
    if before is None or after is None:
        return None
    return {
        "calls": after["calls"] - before["calls"],
        "prompt_tokens": after["prompt_tokens"] - before["prompt_tokens"],
        "completion_tokens": after["completion_tokens"] - before["completion_tokens"],
        "total_tokens": after["total_tokens"] - before["total_tokens"],
        "cost_usd": round(after["cost_usd"] - before["cost_usd"], 6),
        "cost_known": after["cost_known"],
    }


def iter_stages(
    image_bytes: bytes, *, conf: float | None = None, system_name: str | None = None
) -> Iterator[dict]:
    """Roda E1→E4 emitindo um evento (`dict` com `stage`) por etapa.

    Estágios: ``start`` · ``e1`` · ``e2_ocr`` · ``e2_fusion`` · ``e2_crosscheck`` ·
    ``e2_topology`` · ``e3_dfd`` · ``e4_stride`` · ``done``. O evento ``done`` carrega o
    `ThreatModel` final (chave ``threat_model``). Cada evento traz ``elapsed_s`` (tempo do
    estágio) para a UI mostrar onde a latência se concentra (o VLM domina).
    """
    t0 = time.perf_counter()
    name = system_name or "Sistema sob análise"
    yield {"stage": "start", "system_name": name}

    # ── E1 — detecção (obrigatória; lança DetectorUnavailable) ──
    s = time.perf_counter()
    det = detector.detect(image_bytes, conf=conf)
    components = det["components"]
    yield {
        "stage": "e1", "components": components, "annotated_image": det.get("annotated_image"),
        "model": det.get("model", {}), "elapsed_s": round(time.perf_counter() - s, 3),
    }

    # ── E2a — OCR (lê os textos do diagrama) ──
    s = time.perf_counter()
    text_regions: list = []
    ocr_used = False
    if ocr.available():
        try:
            text_regions = ocr.read_text(image_bytes)
            ocr_used = True
        except Exception:  # noqa: BLE001 — OCR é reforço; nunca derruba o pipeline
            text_regions = []
    yield {
        "stage": "e2_ocr", "ocr_used": ocr_used, "text_regions": text_regions,
        "n_text": len(text_regions), "elapsed_s": round(time.perf_counter() - s, 3),
    }

    # ── E2b — fusão ícone↔rótulo (anexa os textos aos componentes) ──
    s = time.perf_counter()
    fused = False
    if text_regions:
        try:
            components = fusion.fuse(components, text_regions)
            fused = True
        except Exception:  # noqa: BLE001
            fused = False
    n_labeled = sum(1 for c in components if c.label)
    yield {
        "stage": "e2_fusion", "fused": fused, "components": components,
        "n_labeled": n_labeled, "elapsed_s": round(time.perf_counter() - s, 3),
    }

    # ── E2c — cross-check + completude (VLM corrige incertos e propõe faltantes) ──
    s = time.perf_counter()
    u0 = provider.current_usage()
    crosscheck_used = False
    n_before = len(components)
    if os.getenv("ARGUS_CROSSCHECK", "1") == "1":
        try:
            components = crosscheck.verify(image_bytes, components)
            crosscheck_used = True
        except Exception:  # noqa: BLE001 — cross-check é reforço; não derruba o pipeline
            crosscheck_used = False
    yield {
        "stage": "e2_crosscheck", "crosscheck_used": crosscheck_used,
        "added": max(0, len(components) - n_before), "components": components,
        "usage_delta": _usage_delta(u0, provider.current_usage()),
        "elapsed_s": round(time.perf_counter() - s, 3),
    }

    # ── E2d — topologia (VLM extrai os fluxos entre componentes) ──
    s = time.perf_counter()
    u0 = provider.current_usage()
    edges = topology.extract(image_bytes, components)
    yield {
        "stage": "e2_topology", "edges": edges, "components": components,
        "n_edges": len(edges), "usage_delta": _usage_delta(u0, provider.current_usage()),
        "elapsed_s": round(time.perf_counter() - s, 3),
    }

    # ── E3 — DFD: marca os fluxos que cruzam fronteiras de confiança ──
    s = time.perf_counter()
    edges = dfd.mark_crossings(components, edges)
    summary = dfd.summarize(components, edges)
    yield {
        "stage": "e3_dfd", "edges": edges, "components": components,
        "summary": summary, "elapsed_s": round(time.perf_counter() - s, 3),
    }

    # ── E4 — STRIDE-per-element ──
    s = time.perf_counter()
    u0 = provider.current_usage()
    threats = stride.generate(components, edges)
    yield {
        "stage": "e4_stride", "n_threats": len(threats),
        "usage_delta": _usage_delta(u0, provider.current_usage()),
        "elapsed_s": round(time.perf_counter() - s, 3),
    }  # a lista completa vai no 'done' (ThreatModel); aqui só a contagem

    # ── E5 — enriquecimento ancorado (CWE/CAPEC/contramedidas) + validação (groundedness) ──
    s = time.perf_counter()
    u0 = provider.current_usage()
    ground: dict = {}
    try:
        ground = enrich.enrich(threats, components, get_store()).as_meta()
    except Exception:  # noqa: BLE001 — E5 é reforço; nunca derruba o pipeline
        ground = {}

    # CVEs reais por componente (cache NVD; sem rede). O ARGUS recupera, não inventa.
    cve_detail: list[dict] = []
    try:
        for c in components:
            cves = kg_cve.cves_for_component(c)
            if cves:
                c.cve_ids = [x["id"] for x in cves]
                cve_detail.append({"component": c.id, "canonical": c.canonical, "label": c.label, "cves": cves})
    except Exception:  # noqa: BLE001
        cve_detail = []
    n_cves = sum(len(d["cves"]) for d in cve_detail)

    yield {
        "stage": "e5_enrich",
        "groundedness": ground.get("groundedness"),
        "id_validity": ground.get("id_validity"),
        "grounded": ground.get("threats_grounded"),
        "ids_valid": ground.get("ids_valid", 0),
        "ids_invalid": ground.get("ids_invalid", 0),
        "sem_candidates": ground.get("sem_candidates", 0),
        "threats_semantic": ground.get("threats_semantic", 0),
        "n_cves": n_cves,
        "cves": cve_detail,
        "usage_delta": _usage_delta(u0, provider.current_usage()),
        "elapsed_s": round(time.perf_counter() - s, 3),
    }

    # ── E6 — scoring DREAD (determinístico, sem LLM) ──
    s = time.perf_counter()
    scoring.apply(threats)
    dread_dist = scoring.distribution(threats)
    yield {"stage": "e6_score", "dread_dist": dread_dist, "elapsed_s": round(time.perf_counter() - s, 3)}

    # ── done — ThreatModel final ──
    cfg = get_config()
    latency = round(time.perf_counter() - t0, 3)
    usage = provider.current_usage()
    tm = ThreatModel(
        system_name=name, components=components, edges=edges, threats=threats,
        meta={
            "system": "argus", "provider": cfg.provider, "model": cfg.model,
            "latency_s": latency, "ocr_used": ocr_used, "threats": len(threats), "n_cves": n_cves,
            "dread_dist": dread_dist,
            **({"usage": usage} if usage is not None else {}), **ground, **summary,
        },
    )
    yield {"stage": "done", "threat_model": tm, "latency_s": latency}


def run(image_bytes: bytes, *, conf: float | None = None, system_name: str | None = None) -> ThreatModel:
    """Caminho não-streaming: consome `iter_stages` e devolve só o `ThreatModel` final.

    Abre um escopo de medição (`provider.meter()`) para que o uso (tokens/custo) seja somado
    ao longo dos estágios e embarcado no `meta.usage` do ThreatModel (igual ao streaming).
    """
    final: ThreatModel | None = None
    with provider.meter():
        for ev in iter_stages(image_bytes, conf=conf, system_name=system_name):
            if ev.get("stage") == "done":
                final = ev["threat_model"]
    if final is None:  # pragma: no cover — iter_stages sempre emite 'done' ou levanta antes
        raise RuntimeError("pipeline ARGUS não produziu ThreatModel")
    return final
