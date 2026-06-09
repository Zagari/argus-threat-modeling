"""Equivalência LocalKG × Neo4jKG (3.8) — exige um Neo4j acessível; PULADO por padrão/CI.

Rode com o profile `full`:
    docker compose --profile full up -d neo4j
    NEO4J_URI=bolt://localhost:7687 NEO4J_AUTH=neo4j/arguspass \
        pytest -m neo4j tests/test_neo4j_equivalence.py
"""

from __future__ import annotations

import os

import pytest

neo4j = pytest.importorskip("neo4j")  # sem o driver (CI) → pula o módulo inteiro

from app.argus.knowledge import seeds  # noqa: E402
from app.argus.knowledge.model import Subgraph  # noqa: E402
from app.argus.knowledge.neo4j_store import Neo4jKG, auth_tuple  # noqa: E402
from app.argus.knowledge.store import LocalKG  # noqa: E402

pytestmark = pytest.mark.neo4j

_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_AUTH = auth_tuple()


def _nodes(sg: Subgraph) -> list[tuple]:
    return sorted((n.kind, n.id, n.name, n.url) for n in sg.nodes)


def _edges(sg: Subgraph) -> list[tuple]:
    return sorted((e.source, e.target, e.type) for e in sg.edges)


@pytest.fixture(scope="module")
def kgs() -> tuple[LocalKG, Neo4jKG]:
    try:
        d = neo4j.GraphDatabase.driver(_URI, auth=_AUTH)
        d.verify_connectivity()
        d.close()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Neo4j indisponível em {_URI}: {e}")
    from app.argus.knowledge.ingest.mirror_neo4j import mirror

    local = LocalKG()
    mirror(local, uri=_URI, auth=_AUTH)
    kg = Neo4jKG(_URI, _AUTH)
    kg.verify()
    return local, kg


@pytest.mark.parametrize("stride", sorted(seeds.STRIDE_TO_CWE))
def test_subgraph_equivalente(kgs: tuple[LocalKG, Neo4jKG], stride: str) -> None:
    local, kg = kgs
    a = local.subgraph("api_gateway", stride)
    b = kg.subgraph("api_gateway", stride)
    assert _nodes(a) == _nodes(b), f"nós divergem em {stride}"
    assert _edges(a) == _edges(b), f"arestas divergem em {stride}"
