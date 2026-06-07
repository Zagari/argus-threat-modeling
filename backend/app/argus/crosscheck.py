"""E2 — Cross-check de classificação + completude via VLM.

Depois do detector (E1) e da fusão com OCR (E2a), o VLM relê o diagrama e, na MESMA
chamada: (1) corrige a classe dos componentes INCERTOS (confiança visual baixa),
preservando as detecções fortes do E1; e (2) PROPÕE componentes claramente presentes que o
detector não encontrou (ex.: um ícone que o modelo sintético não reconhece). Componentes
propostos vêm com `confidence=None` (sinal de "veio do VLM, não do detector") e bbox
aproximado — revisáveis na UI.

Roda em qualquer ambiente (só precisa da chave do LLM); em modo mock, é no-op.
"""

from __future__ import annotations

import os
import re

from pydantic import BaseModel, Field

from app.argus.labelmap import match_label
from app.config import get_config
from app.llm import provider
from app.schemas import Component
from app.taxonomy import CANONICAL_CLASSES, CANONICAL_ELEMENT_TYPE

_SYSTEM = (
    "Você é um especialista em arquiteturas de nuvem (AWS/Azure/GCP) que classifica "
    "componentes de diagramas em classes canônicas. Responda sempre em português."
)

_PROMPT = """Recebe a imagem de um diagrama de arquitetura e a lista de componentes já \
detectados (id, classe atual, posição, rótulo). Use EXCLUSIVAMENTE estas classes canônicas:
{classes}

Componentes detectados (id | classe atual | bbox [x,y,w,h] normalizado | rótulo):
{components}

Faça DUAS coisas:
1) `components`: para CADA id acima, a classe canônica correta (repita se já estiver certa).
2) `missing`: componentes CLARAMENTE presentes no diagrama que NÃO estão na lista acima.
   Para cada um: a classe (da lista), o bbox aproximado [x,y,w,h] normalizado em 0..1, e o
   rótulo lido. Seja conservador — só inclua o que tem certeza que existe e ficou de fora.

Use os mesmos ids existentes; não invente ids para os já detectados."""


class _Vote(BaseModel):
    id: str
    canonical: str


class _Missing(BaseModel):
    canonical: str
    bbox: list[float] = Field(default_factory=list)
    label: str | None = None


class _Result(BaseModel):
    components: list[_Vote] = Field(default_factory=list)
    missing: list[_Missing] = Field(default_factory=list)


def _valid_bbox(b: list[float]) -> list[float] | None:
    if not isinstance(b, list) or len(b) != 4:
        return None
    try:
        x, y, w, h = (float(v) for v in b)
    except (TypeError, ValueError):
        return None
    x, y = min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)
    w, h = min(max(w, 0.001), 1.0), min(max(h, 0.001), 1.0)
    return [round(x, 5), round(y, 5), round(w, 5), round(h, 5)]


def _too_close(bbox: list[float], comps: list[Component], dist: float) -> bool:
    """Dedup por DISTÂNCIA entre centros (robusto à bbox aproximada do VLM)."""
    cx, cy = bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2
    for c in comps:
        if c.bbox and len(c.bbox) == 4:
            ex, ey = c.bbox[0] + c.bbox[2] / 2, c.bbox[1] + c.bbox[3] / 2
            if ((cx - ex) ** 2 + (cy - ey) ** 2) ** 0.5 < dist:
                return True
    return False


def _next_index(components: list[Component]) -> int:
    mx = 0
    for c in components:
        m = re.fullmatch(r"C(\d+)", c.id)
        if m:
            mx = max(mx, int(m.group(1)))
    return mx + 1


def verify(image_bytes: bytes, components: list[Component], *, mime: str = "image/jpeg") -> list[Component]:
    """Corrige classes incertas e adiciona componentes faltantes propostos pelo VLM."""
    cfg = get_config()
    if cfg.mock or not components:
        return components

    conf_thr = float(os.getenv("ARGUS_CROSSCHECK_CONF", "0.75"))
    propose_missing = os.getenv("ARGUS_CROSSCHECK_PROPOSE", "1") == "1"
    valid = set(CANONICAL_CLASSES)
    lines = "\n".join(
        f"- {c.id} | {c.canonical} | {[round(v, 2) for v in (c.bbox or [])]} | {c.label or '-'}"
        for c in components
    )
    prompt = _PROMPT.format(classes=", ".join(CANONICAL_CLASSES), components=lines)
    res: _Result = provider.vision(  # type: ignore[assignment]
        image_bytes, prompt, response_model=_Result, mime=mime, system=_SYSTEM, temperature=0.0
    )
    vote_map = {v.id: v.canonical for v in res.components if v.canonical in valid}

    # 1) corrige classes incertas (não sobrescreve detecção forte)
    out: list[Component] = []
    for c in components:
        new = c.model_copy()
        vc = vote_map.get(c.id)
        cur_conf = c.confidence if c.confidence is not None else 1.0
        if vc and vc != c.canonical and cur_conf < conf_thr:
            new.canonical = vc
            new.element_type = CANONICAL_ELEMENT_TYPE.get(vc, new.element_type)  # type: ignore[assignment]
        out.append(new)

    # 2) adiciona componentes faltantes propostos pelo VLM (deduplicados vs existentes)
    if propose_missing:
        dedup_dist = float(os.getenv("ARGUS_CROSSCHECK_DEDUP", "0.07"))
        idx = _next_index(out)
        for m in res.missing:
            bbox = _valid_bbox(m.bbox)
            if not bbox or _too_close(bbox, out, dedup_dist):
                continue
            # o rótulo, quando mapeia para uma classe, vence o palpite de classe do VLM
            # (ex.: "Logic Apps" -> serverless_fn, não compute)
            cls = match_label(m.label or "") or m.canonical
            if cls not in valid:
                continue
            out.append(
                Component(
                    id=f"C{idx}",
                    canonical=cls,
                    label=m.label,
                    element_type=CANONICAL_ELEMENT_TYPE.get(cls, "Process"),  # type: ignore[arg-type]
                    bbox=bbox,
                    confidence=None,  # proposto pelo VLM (não pelo detector) — revisável
                )
            )
            idx += 1
    return out
