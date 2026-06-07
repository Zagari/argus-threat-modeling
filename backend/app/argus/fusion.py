"""E2 — Fusão ícone+rótulo.

Combina os componentes do detector visual (E1) com o texto do OCR: preenche
`Component.label` com o rótulo mais próximo e, quando o texto indica outra classe (via
sinônimos do `mapeamento.yaml`), corrige a classe. É o mecanismo que ataca a
**lacuna sintético-real** (ex.: um ícone classificado como `actor_user` mas rotulado
``Application Load Balancer'' vira `load_balancer`).

Política (`ARGUS_FUSION_POLICY`):
  - `label_wins` (default): se o texto casa numa classe conhecida, o texto vence
    (o rótulo do componente costuma ser a verdade no diagrama).
  - `low_conf`: só corrige quando a confiança visual < `ARGUS_FUSION_CONF` (default 0,6).

Módulo puro (sem dependências de ML) — daí ser facilmente testável.
"""

from __future__ import annotations

import os

from app.argus.labelmap import match_label
from app.schemas import Component, TextRegion
from app.taxonomy import CANONICAL_ELEMENT_TYPE


def _center(bbox: list[float]) -> tuple[float, float]:
    return bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2


def _dist_to_box(point: tuple[float, float], bbox: list[float]) -> float:
    """Distância do ponto à caixa (0 se dentro). Trata legenda ABAIXO ou AO LADO do ícone."""
    px, py = point
    x, y, w, h = bbox
    dx = max(x - px, 0.0, px - (x + w))
    dy = max(y - py, 0.0, py - (y + h))
    return (dx * dx + dy * dy) ** 0.5


def _assign_regions(components: list[Component], regions: list[TextRegion], max_dist: float) -> list[list[TextRegion]]:
    """Atribui cada trecho de texto ao componente MAIS PRÓXIMO (dentro de `max_dist`).

    Mais robusto que olhar só ``dentro/abaixo``: captura legendas ao lado do ícone
    (ex.: ``Resource group``) e reconstrói legendas multi-palavra fragmentadas pelo OCR.
    """
    buckets: list[list[TextRegion]] = [[] for _ in components]
    for r in regions:
        if not r.bbox or len(r.bbox) < 4:
            continue
        rc = _center(r.bbox)
        best_i, best_d = -1, max_dist
        for i, c in enumerate(components):
            if not c.bbox or len(c.bbox) < 4:
                continue
            d = _dist_to_box(rc, c.bbox)
            if d < best_d:
                best_d, best_i = d, i
        if best_i >= 0:
            buckets[best_i].append(r)
    return buckets


def fuse(components: list[Component], regions: list[TextRegion]) -> list[Component]:
    """Retorna novos componentes com `label` preenchido e classe corrigida quando cabe."""
    policy = os.getenv("ARGUS_FUSION_POLICY", "label_wins").lower()
    conf_thr = float(os.getenv("ARGUS_FUSION_CONF", "0.6"))
    max_dist = float(os.getenv("ARGUS_FUSION_MAXDIST", "0.06"))
    buckets = _assign_regions(components, regions, max_dist)
    out: list[Component] = []
    for c, bucket in zip(components, buckets, strict=True):
        new = c.model_copy()
        if bucket:
            bucket.sort(key=lambda r: (round(r.bbox[1], 3), r.bbox[0]))  # por linha (y), depois x
            text = " ".join(r.text for r in bucket).strip()
            if text:
                new.label = text
                lc = match_label(text)
                if lc and lc != c.canonical:
                    visual_conf = c.confidence if c.confidence is not None else 1.0
                    take_label = policy == "label_wins" or visual_conf < conf_thr
                    if take_label:
                        new.canonical = lc
                        new.element_type = CANONICAL_ELEMENT_TYPE.get(lc, new.element_type)  # type: ignore[assignment]
        out.append(new)
    return out
