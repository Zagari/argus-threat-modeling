"""`Neo4jKG` — backend de grafo (Cypher) que implementa o MESMO contrato do `LocalKG`.

OPT-IN via `ARGUS_KG_BACKEND=neo4j`; se o driver ou a instância faltarem, `get_store()` cai
graciosamente no `LocalKG` (fonte de verdade). O grafo é um ESPELHO do `LocalKG`
(ver `ingest/mirror_neo4j.py`): a equivalência dos subgrafos é garantida por construção —
usamos o mesmo `build_subgraph` (sementes + tetos), só trocando a fonte dos vizinhos por
consultas Cypher ordenadas pela propriedade `ord` (preserva a ordem original do LocalKG).

Os atributos dos nós (name/url/text/stride) são carregados uma vez em memória no `verify()`
(grafo pequeno, ~milhares de nós) e servem `name_url`/`exists`/`entity`/`iter_entities`; a
TRAVESSIA (multi-hop) é que roda em Cypher — é o "Graph-RAG de verdade".
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

from app.argus.knowledge.model import Entity, Subgraph
from app.argus.knowledge.store import build_subgraph

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_AUTH = os.getenv("NEO4J_AUTH", "neo4j/arguspass")


def auth_tuple(auth: str | None = None) -> tuple[str, str]:
    """'user/senha' → ('user', 'senha') (formato compatível com NEO4J_AUTH do compose)."""
    user, _, pwd = (auth or NEO4J_AUTH).partition("/")
    return (user, pwd)


class Neo4jKG:
    def __init__(self, uri: str | None = None, auth: tuple[str, str] | None = None) -> None:
        import neo4j  # lazy — só quando o backend neo4j é selecionado

        self._driver: Any = neo4j.GraphDatabase.driver(uri or NEO4J_URI, auth=auth or auth_tuple())
        self._nodes: dict[tuple[str, str], Entity] = {}

    def verify(self) -> None:
        """Confirma a conectividade e carrega os atributos dos nós. Levanta se indisponível."""
        self._driver.verify_connectivity()
        self._load_nodes()

    def close(self) -> None:
        self._driver.close()

    def _load_nodes(self) -> None:
        q = ("MATCH (n:Entity) WHERE n.phantom IS NULL "
             "RETURN n.kind AS kind, n.id AS id, n.name AS name, n.url AS url, n.text AS text, n.stride AS stride")
        with self._driver.session() as s:
            for r in s.run(q):
                e = Entity(id=r["id"], kind=r["kind"], name=r["name"] or "", url=r["url"],
                           text=r["text"] or "", stride=list(r["stride"] or []))
                self._nodes[(e.kind, e.id)] = e

    # ── _Neighbors (vizinhos via Cypher, ordenados por `ord`) ────────────────────
    def _neighbors(self, rel: str, src_kind: str, src_id: str, dst_kind: str) -> list[str]:
        q = (f"MATCH (a:Entity {{kind:$sk, id:$sid}})-[r:{rel}]->(b:Entity {{kind:$dk}}) "
             "RETURN b.id AS id ORDER BY r.ord")
        with self._driver.session() as s:
            return [r["id"] for r in s.run(q, sk=src_kind, sid=src_id, dk=dst_kind)]

    def name_url(self, kind: str, eid: str) -> tuple[str, str | None]:
        e = self._nodes.get((kind, eid))
        return (e.name, e.url) if e else ("", None)

    def capec_by_cwe(self, cwe: str) -> list[str]:
        return self._neighbors("EXPLOITED_BY", "CWE", cwe, "CAPEC")

    def attack_by_capec(self, capec: str) -> list[str]:
        return self._neighbors("MAPS_TO", "CAPEC", capec, "ATTACK")

    def d3fend_by_attack(self, atk: str) -> list[str]:
        return self._neighbors("COUNTERED_BY", "ATTACK", atk, "D3FEND")

    def reqs_by_chapter(self, chapter: str) -> list[str]:
        return self._neighbors("REQUIRES", "Control", chapter, "Control")

    # ── contrato KnowledgeStore ──────────────────────────────────────────────────
    def subgraph(self, canonical: str, stride: str) -> Subgraph:
        return build_subgraph(canonical, stride, self)

    def exists(self, kind: str, id: str) -> bool:
        return (kind, id) in self._nodes

    def entity(self, kind: str, id: str) -> Entity | None:
        return self._nodes.get((kind, id))

    def iter_entities(self) -> Iterator[Entity]:
        yield from self._nodes.values()
