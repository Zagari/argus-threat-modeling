"""Endpoints de exploração da base de conhecimento (E5) — subgrafo, entidade, busca, opções.

Servem o Knowledge Explorer da UI e o painel de subgrafo. Leem o `KnowledgeStore` (LocalKG),
sem rede. A busca aqui é por substring (determinística); a busca semântica (Chroma) entra no 3.7.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.argus.knowledge.model import Entity, Subgraph
from app.argus.knowledge.store import get_store
from app.taxonomy import CANONICAL_CLASSES

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_STRIDE = [
    "Spoofing", "Tampering", "Repudiation",
    "Information Disclosure", "Denial of Service", "Elevation of Privilege",
]


@router.get("/options")
def options() -> dict:
    """Listas para os seletores do Explorer: classes canônicas e categorias STRIDE."""
    return {"classes": CANONICAL_CLASSES, "stride": _STRIDE}


@router.get("/subgraph", response_model=Subgraph)
def subgraph(
    canonical: str = Query(..., description="classe canônica"),
    stride: str = Query(..., description="categoria STRIDE"),
) -> Subgraph:
    return get_store().subgraph(canonical, stride)


@router.get("/entity/{kind}/{eid}", response_model=Entity)
def entity(kind: str, eid: str) -> Entity:
    e = get_store().entity(kind, eid)
    if e is None:
        raise HTTPException(status_code=404, detail=f"entidade não encontrada: {kind} {eid}")
    return e


@router.get("/search")
def search(q: str = Query(..., min_length=2), limit: int = Query(25, ge=1, le=100)) -> list[dict]:
    """Busca por substring em id/nome (determinística). Útil para o Knowledge Explorer."""
    ql = q.lower()
    out: list[dict] = []
    for e in get_store().iter_entities():
        if ql in e.id.lower() or ql in e.name.lower():
            out.append({"id": e.id, "kind": e.kind, "name": e.name, "url": e.url})
            if len(out) >= limit:
                break
    return out
