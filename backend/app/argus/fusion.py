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


def _label_text(comp: Component, regions: list[TextRegion]) -> str | None:
    """Reconstrói a legenda: junta TODOS os trechos de texto dentro do componente ou logo
    abaixo dele (o OCR costuma quebrar legendas multi-palavra em vários trechos)."""
    if not comp.bbox or len(comp.bbox) < 4:
        return None
    x, y, w, h = comp.bbox
    picked: list[TextRegion] = []
    for r in regions:
        if not r.bbox or len(r.bbox) < 4:
            continue
        rx, ry = _center(r.bbox)
        inside = (x <= rx <= x + w) and (y <= ry <= y + h)
        below = (x - 0.01 <= rx <= x + w + 0.01) and (y + h <= ry <= y + h + 0.07)
        if inside or below:
            picked.append(r)
    if not picked:
        return None
    picked.sort(key=lambda r: (round(r.bbox[1], 3), r.bbox[0]))  # por linha (y), depois x
    return " ".join(r.text for r in picked).strip() or None


def fuse(components: list[Component], regions: list[TextRegion]) -> list[Component]:
    """Retorna novos componentes com `label` preenchido e classe corrigida quando cabe."""
    policy = os.getenv("ARGUS_FUSION_POLICY", "label_wins").lower()
    conf_thr = float(os.getenv("ARGUS_FUSION_CONF", "0.6"))
    out: list[Component] = []
    for c in components:
        new = c.model_copy()
        text = _label_text(c, regions)
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
