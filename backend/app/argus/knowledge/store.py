"""`KnowledgeStore` (contrato) + `LocalKG` (adaptador em memória — default e fallback).

`LocalKG` é a fonte de verdade portátil: carrega as **sementes** (sempre) e *sobrepõe* os
catálogos normalizados (`data/knowledge/normalized/*.json`) quando presentes. Expõe:
  - `subgraph(canonical, stride)` — vizinhança citável (CWE→CAPEC + controles ASVS) p/ o E5;
  - `exists(kind, id)` — validação de id (anti-alucinação);
  - `entity(kind, id)` / `iter_entities()` — citação e indexação (Chroma, 3.7).

Neo4jKG (3.8) implementa o mesmo contrato via Cypher; o local segue como fallback equivalente.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.argus.knowledge import seeds
from app.argus.knowledge.model import (
    KIND_ATTACK,
    KIND_CAPEC,
    KIND_CONTROL,
    KIND_CWE,
    KIND_D3FEND,
    Entity,
    Subgraph,
    SubgraphEdge,
    SubgraphNode,
)

# Catálogos versionados DENTRO do pacote → seguem a imagem Docker (COPY backend/) e o
# pip install (HF Spaces), sem depender do CWD nem da árvore do repo.
_DEFAULT_DIR = Path(__file__).resolve().parent / "catalog"


def _normalized_dir() -> Path:
    return Path(os.getenv("ARGUS_KNOWLEDGE_DIR", str(_DEFAULT_DIR)))

# Quantos CAPECs por CWE / requisitos ASVS por capítulo entram no subgrafo (limita o contexto).
_MAX_CAPEC_PER_CWE = int(os.getenv("ARGUS_KG_CAPEC_PER_CWE", "3"))
_MAX_ASVS_REQ = int(os.getenv("ARGUS_KG_ASVS_REQS", "3"))
_MAX_ATTACK_PER_CAPEC = int(os.getenv("ARGUS_KG_ATTACK_PER_CAPEC", "1"))
_MAX_D3FEND_PER_ATTACK = int(os.getenv("ARGUS_KG_D3FEND_PER_ATTACK", "1"))


@runtime_checkable
class KnowledgeStore(Protocol):
    def subgraph(self, canonical: str, stride: str) -> Subgraph: ...
    def exists(self, kind: str, id: str) -> bool: ...
    def entity(self, kind: str, id: str) -> Entity | None: ...
    def iter_entities(self) -> Iterator[Entity]: ...


class LocalKG:
    """Grafo de conhecimento em memória (dicts indexados por (kind, id))."""

    def __init__(self, normalized_dir: Path | None = None) -> None:
        self._dir = normalized_dir or _normalized_dir()
        self._by: dict[tuple[str, str], Entity] = {}
        self._capec_by_cwe: dict[str, list[str]] = {}
        self._reqs_by_chapter: dict[str, list[str]] = {}  # ASVS: capítulo → requisitos finos
        self._attack_by_capec: dict[str, list[str]] = {}  # CAPEC → técnicas ATT&CK
        self._d3fend_by_attack: dict[str, list[str]] = {}  # ATT&CK → defesas D3FEND
        self._loaded = False

    # ── carga ────────────────────────────────────────────────────────────────
    def _put(self, e: Entity) -> None:
        self._by[(e.kind, e.id)] = e

    def _ensure(self) -> None:
        if self._loaded:
            return
        self._load_seeds()
        self._load_normalized()
        self._index_capec_links()
        self._index_asvs_reqs()
        self._index_chains()
        self._loaded = True

    def _load_seeds(self) -> None:
        cwe_stride: dict[str, set[str]] = {}
        for stride, cwes in seeds.STRIDE_TO_CWE.items():
            for c in cwes:
                cwe_stride.setdefault(c, set()).add(stride)
        for cwe, strides in cwe_stride.items():
            self._put(Entity(id=cwe, kind=KIND_CWE, name=seeds.CWE_NAMES.get(cwe, ""),
                             url=seeds.cwe_url(cwe), stride=sorted(strides)))

        asvs_stride: dict[str, set[str]] = {}
        for stride, ids in seeds.STRIDE_TO_ASVS.items():
            for a in ids:
                asvs_stride.setdefault(a, set()).add(stride)
        for aid, name in seeds.ASVS_CHAPTERS.items():
            self._put(Entity(id=aid, kind=KIND_CONTROL, name=name, url=seeds.asvs_url(aid),
                             stride=sorted(asvs_stride.get(aid, set()))))

        nist_stride: dict[str, set[str]] = {}
        for stride, ids in seeds.STRIDE_TO_NIST.items():
            for nid in ids:
                nist_stride.setdefault(nid, set()).add(stride)
        for nid, strides in nist_stride.items():  # nome real vem do catálogo (overlay)
            self._put(Entity(id=nid, kind=KIND_CONTROL, name="", url=seeds.nist_url(nid), stride=sorted(strides)))

    def _load_normalized(self) -> None:
        for fname in ("cwe.json", "capec.json", "asvs.json", "attack.json", "d3fend.json", "nist80053.json"):
            p = self._dir / fname
            if not p.exists():
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for d in data:
                try:
                    e = Entity(**d)
                except (TypeError, ValueError):
                    continue
                prev = self._by.get((e.kind, e.id))
                if prev:  # catálogo completa a semente sem perder o que a semente sabia
                    if not e.name:
                        e.name = prev.name
                    if not e.stride:
                        e.stride = prev.stride
                self._put(e)

    def _index_capec_links(self) -> None:
        for (kind, _id), e in self._by.items():
            if kind != KIND_CAPEC:
                continue
            for r in e.rels:
                if r.type == "TARGETS" and r.target_kind == KIND_CWE:
                    self._capec_by_cwe.setdefault(r.target_id, []).append(e.id)

    def _index_asvs_reqs(self) -> None:
        """Agrupa os requisitos ASVS finos (ASVS-V2.1.1) sob o capítulo (ASVS-V2)."""
        for kind, cid in self._by:
            if kind != KIND_CONTROL or not cid.startswith("ASVS-V"):
                continue
            rest = cid[len("ASVS-V") :]  # '2.1.1' (requisito) ou '2' (capítulo)
            if "." in rest:
                self._reqs_by_chapter.setdefault(f"ASVS-V{rest.split('.')[0]}", []).append(cid)

    def _index_chains(self) -> None:
        """CAPEC→ATT&CK (rels MAPS_TO) e ATT&CK→D3FEND (rels COUNTERS, invertido)."""
        for (kind, _id), e in self._by.items():
            if kind == KIND_CAPEC:
                for r in e.rels:
                    if r.type == "MAPS_TO" and r.target_kind == KIND_ATTACK:
                        self._attack_by_capec.setdefault(e.id, []).append(r.target_id)
            elif kind == KIND_D3FEND:
                for r in e.rels:
                    if r.type == "COUNTERS" and r.target_kind == KIND_ATTACK:
                        self._d3fend_by_attack.setdefault(r.target_id, []).append(e.id)

    # ── contrato ───────────────────────────────────────────────────────────────
    def exists(self, kind: str, id: str) -> bool:
        self._ensure()
        return (kind, id) in self._by

    def entity(self, kind: str, id: str) -> Entity | None:
        self._ensure()
        return self._by.get((kind, id))

    def iter_entities(self) -> Iterator[Entity]:
        self._ensure()
        yield from self._by.values()

    def subgraph(self, canonical: str, stride: str) -> Subgraph:
        self._ensure()
        sg = Subgraph(canonical=canonical, stride=stride)
        stride_id = f"STRIDE:{stride}"
        sg.nodes.append(SubgraphNode(id=stride_id, kind="Stride", name=stride))
        seen: set[tuple[str, str]] = {("Stride", stride_id)}

        def add(kind: str, eid: str) -> None:
            if (kind, eid) in seen:
                return
            seen.add((kind, eid))
            e = self._by.get((kind, eid))
            sg.nodes.append(SubgraphNode(id=eid, kind=kind, name=e.name if e else "", url=e.url if e else None))

        for cwe in seeds.STRIDE_TO_CWE.get(stride, []):
            add(KIND_CWE, cwe)
            sg.edges.append(SubgraphEdge(source=stride_id, target=cwe, type="REALIZED_BY"))
            for capec in self._capec_by_cwe.get(cwe, [])[:_MAX_CAPEC_PER_CWE]:
                add(KIND_CAPEC, capec)
                sg.edges.append(SubgraphEdge(source=cwe, target=capec, type="EXPLOITED_BY"))
                for atk in self._attack_by_capec.get(capec, [])[:_MAX_ATTACK_PER_CAPEC]:  # ATT&CK
                    add(KIND_ATTACK, atk)
                    sg.edges.append(SubgraphEdge(source=capec, target=atk, type="MAPS_TO"))
                    for dfd in self._d3fend_by_attack.get(atk, [])[:_MAX_D3FEND_PER_ATTACK]:  # D3FEND
                        add(KIND_D3FEND, dfd)
                        sg.edges.append(SubgraphEdge(source=atk, target=dfd, type="COUNTERED_BY"))

        for ctrl in seeds.STRIDE_TO_ASVS.get(stride, []):
            add(KIND_CONTROL, ctrl)
            sg.edges.append(SubgraphEdge(source=stride_id, target=ctrl, type="MITIGATED_BY"))
            for req in self._reqs_by_chapter.get(ctrl, [])[:_MAX_ASVS_REQ]:  # requisitos ASVS finos
                add(KIND_CONTROL, req)
                sg.edges.append(SubgraphEdge(source=ctrl, target=req, type="REQUIRES"))

        for nctrl in seeds.STRIDE_TO_NIST.get(stride, []):  # controles NIST 800-53
            add(KIND_CONTROL, nctrl)
            sg.edges.append(SubgraphEdge(source=stride_id, target=nctrl, type="MITIGATED_BY"))

        return sg


_store: LocalKG | None = None


def get_store() -> KnowledgeStore:
    """Backend ativo. Por ora sempre `LocalKG` (Neo4jKG entra no 3.8 via ARGUS_KG_BACKEND)."""
    global _store
    if _store is None:
        _store = LocalKG()
    return _store
