"""Espelha o `LocalKG` (fonte de verdade) para um Neo4j — idempotente (recria do zero).

Catálogo → nós `:Entity {kind,id,name,url,text,stride}`; cadeias com a propriedade `ord`
(posição na lista do LocalKG) p/ que o Cypher reproduza EXATAMENTE os mesmos tetos/ordem.
Os nós `:Stride` e as arestas STRIDE→{CWE,Control} são criados só para a VISUALIZAÇÃO no
Neo4j Browser (o `build_subgraph` usa as sementes, não o grafo, para essa camada).

Uso:
    NEO4J_URI=bolt://localhost:7687 NEO4J_AUTH=neo4j/arguspass \
        python -m app.argus.knowledge.ingest.mirror_neo4j
"""

from __future__ import annotations

from typing import Any

from app.argus.knowledge import seeds
from app.argus.knowledge.model import (
    KIND_ATTACK,
    KIND_CAPEC,
    KIND_CONTROL,
    KIND_CWE,
    KIND_D3FEND,
)
from app.argus.knowledge.neo4j_store import NEO4J_URI, auth_tuple
from app.argus.knowledge.store import LocalKG


def _rels(session: Any, rows: list[dict], rtype: str) -> None:
    """Cria arestas :Entity-[rtype {ord}]->:Entity em lote (UNWIND)."""
    if not rows:
        return
    session.run(
        f"UNWIND $rows AS r "
        f"MATCH (a:Entity {{kind:r.sk, id:r.sid}}), (b:Entity {{kind:r.dk, id:r.did}}) "
        f"CREATE (a)-[:{rtype} {{ord:r.ord}}]->(b)",
        rows=rows,
    )


def _stride_rels(session: Any, rows: list[dict], rtype: str) -> None:
    """Cria arestas :Stride-[rtype {ord}]->:Entity (apenas p/ visualização)."""
    if not rows:
        return
    session.run(
        f"UNWIND $rows AS r "
        f"MATCH (a:Stride {{id:r.sid}}), (b:Entity {{kind:r.dk, id:r.did}}) "
        f"CREATE (a)-[:{rtype} {{ord:r.ord}}]->(b)",
        rows=rows,
    )


def mirror(local: LocalKG, *, uri: str | None = None, auth: tuple[str, str] | None = None) -> dict[str, int]:
    """Recria o grafo no Neo4j a partir do `local`. Devolve contagens. Idempotente."""
    import neo4j  # lazy — só quando se usa o backend de grafo

    nodes = [{"kind": e.kind, "id": e.id, "name": e.name, "url": e.url, "text": e.text, "stride": e.stride}
             for e in local.iter_entities()]

    stride_names = sorted(set(seeds.STRIDE_TO_CWE) | set(seeds.STRIDE_TO_ASVS) | set(seeds.STRIDE_TO_NIST))
    stride_nodes = [{"id": f"STRIDE:{st}", "name": st} for st in stride_names]

    # Cadeias a partir dos mapas de adjacência crus (preserva chaves/alvos órfãos e a ordem):
    adj = local.adjacency()
    specs = [
        ("capec_by_cwe", KIND_CWE, KIND_CAPEC, "EXPLOITED_BY"),
        ("attack_by_capec", KIND_CAPEC, KIND_ATTACK, "MAPS_TO"),
        ("d3fend_by_attack", KIND_ATTACK, KIND_D3FEND, "COUNTERED_BY"),
        ("reqs_by_chapter", KIND_CONTROL, KIND_CONTROL, "REQUIRES"),
    ]
    chains: dict[str, list[dict]] = {}
    for key, sk, dk, rtype in specs:
        rows: list[dict] = []
        for sid, targets in adj[key].items():
            for i, did in enumerate(targets):
                rows.append({"sk": sk, "sid": sid, "dk": dk, "did": did, "ord": i})
        chains[rtype] = rows

    realized, mitigated = [], []  # type: ignore[var-annotated]
    for st, cwes in seeds.STRIDE_TO_CWE.items():
        for i, c in enumerate(cwes):
            realized.append({"sid": f"STRIDE:{st}", "dk": KIND_CWE, "did": c, "ord": i})
    for mapping in (seeds.STRIDE_TO_ASVS, seeds.STRIDE_TO_NIST):
        for st, ids in mapping.items():
            for i, cid in enumerate(ids):
                mitigated.append({"sid": f"STRIDE:{st}", "dk": KIND_CONTROL, "did": cid, "ord": i})

    # Nós placeholder p/ ids referenciados nas cadeias mas sem entrada de catálogo (ex.: ATT&CK
    # não ingerida): assim a aresta+ord existe e o subgrafo bate com o LocalKG. Marcados `phantom`
    # → o Neo4jKG os EXCLUI do cache de nós (exists/entity/iter_entities seguem idênticos).
    node_keys = {(e.kind, e.id) for e in local.iter_entities()}
    refs: set[tuple[str, str]] = set()
    for rws in chains.values():
        for r in rws:
            refs.add((r["sk"], r["sid"]))
            refs.add((r["dk"], r["did"]))
    phantoms = [{"kind": k, "id": i} for (k, i) in sorted(refs - node_keys)]

    driver = neo4j.GraphDatabase.driver(uri or NEO4J_URI, auth=auth or auth_tuple())
    try:
        with driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")
            s.run("CREATE INDEX entity_key IF NOT EXISTS FOR (n:Entity) ON (n.kind, n.id)")
            s.run("UNWIND $rows AS r CREATE (n:Entity) SET n = r", rows=nodes)
            s.run("UNWIND $rows AS r CREATE (n:Stride {id:r.id, name:r.name})", rows=stride_nodes)
            if phantoms:
                s.run("UNWIND $rows AS r CREATE (n:Entity {kind:r.kind, id:r.id, phantom:true})", rows=phantoms)
            for rtype, rws in chains.items():
                _rels(s, rws, rtype)
            _stride_rels(s, realized, "REALIZED_BY")
            _stride_rels(s, mitigated, "MITIGATED_BY")
    finally:
        driver.close()

    rels = sum(len(v) for v in chains.values()) + len(realized) + len(mitigated)
    return {"nodes": len(nodes), "phantom": len(phantoms), "stride": len(stride_nodes), "rels": rels}


def main() -> None:
    counts = mirror(LocalKG())
    print(f"Neo4j espelhado: {counts}")


if __name__ == "__main__":
    main()
