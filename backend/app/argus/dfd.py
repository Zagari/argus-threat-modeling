"""E3 — DFD: tipagem do grafo + marcação de fronteiras de confiança.

O grafo do E2 já vem tipado (cada `Component.element_type` vem da taxonomia canônica). O E3
acrescenta a dimensão que importa para a modelagem de ameaças: a **contenção** (quais
componentes estão dentro de cada `trust_boundary`) e a marcação de
`Edge.crosses_boundary` --- um fluxo cruza uma fronteira quando origem e destino estão em
zonas de confiança DIFERENTES. Esses fluxos são os candidatos número um a ameaças
(spoofing/tampering/information disclosure).

Módulo puro (sem ML/LLM) — determinístico e testável.
"""

from __future__ import annotations

from app.schemas import Component, Edge


def _center(bbox: list[float]) -> tuple[float, float]:
    return bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2


def _inside(comp: Component, boundary: Component) -> bool:
    """True se o centro de `comp` cai dentro da bbox da `boundary`."""
    if not comp.bbox or len(comp.bbox) < 4 or not boundary.bbox or len(boundary.bbox) < 4:
        return False
    cx, cy = _center(comp.bbox)
    x, y, w, h = boundary.bbox
    return x <= cx <= x + w and y <= cy <= y + h


def containment(components: list[Component]) -> dict[str, set[str]]:
    """`component_id` -> conjunto de ids de `trust_boundary` que o contêm."""
    boundaries = [c for c in components if c.element_type == "TrustBoundary"]
    out: dict[str, set[str]] = {}
    for c in components:
        if c.element_type == "TrustBoundary":
            continue
        out[c.id] = {b.id for b in boundaries if b.id != c.id and _inside(c, b)}
    return out


def mark_crossings(components: list[Component], edges: list[Edge]) -> list[Edge]:
    """Marca `crosses_boundary` quando origem e destino estão em zonas de confiança distintas."""
    contain = containment(components)
    out: list[Edge] = []
    for e in edges:
        new = e.model_copy()
        new.crosses_boundary = contain.get(e.source, set()) != contain.get(e.target, set())
        out.append(new)
    return out


def summarize(components: list[Component], edges: list[Edge]) -> dict:
    """Resumo do DFD para a `meta` do resultado."""
    counts: dict[str, int] = {}
    for c in components:
        counts[c.element_type] = counts.get(c.element_type, 0) + 1
    return {
        "by_element_type": counts,
        "boundaries": counts.get("TrustBoundary", 0),
        "crossing_flows": sum(1 for e in edges if e.crosses_boundary),
    }
