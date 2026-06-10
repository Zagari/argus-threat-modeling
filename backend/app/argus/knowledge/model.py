"""Modelos do grafo de conhecimento — entidades, relações e subgrafo citável.

Esquema (ver PROPOSTA §15.1): nós CWE/CAPEC/ATTACK/D3FEND/Control(ASVS/NIST)/CVE/Stride/Component
e relações REALIZED_BY/EXPLOITED_BY/MAPS_TO/MITIGATED_BY/COUNTERED_BY/INSTANCE_OF/HAS_CPE.
As entidades são serializadas como JSON normalizado em `data/knowledge/normalized/`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# Tipos de nó do grafo de conhecimento.
KIND_CWE = "CWE"
KIND_CAPEC = "CAPEC"
KIND_ATTACK = "ATTACK"
KIND_D3FEND = "D3FEND"
KIND_CONTROL = "Control"  # ASVS / NIST / CIS
KIND_CVE = "CVE"


class Relation(BaseModel):
    """Aresta dirigida de uma entidade para outra (ex.: CAPEC -TARGETS-> CWE)."""

    type: str
    target_kind: str
    target_id: str


class Entity(BaseModel):
    """Nó do grafo (uma fraqueza, padrão de ataque, controle…), citável por id+url."""

    id: str
    kind: str
    name: str = ""
    text: str = ""
    url: str | None = None
    rank: int = 0  # relevância intrínseca do catálogo (3.10): ordena candidatos antes do corte por salto
    stride: list[str] = Field(default_factory=list, description="Categorias STRIDE associadas (quando houver).")
    rels: list[Relation] = Field(default_factory=list)


class SubgraphNode(BaseModel):
    id: str
    kind: str
    name: str = ""
    url: str | None = None


class SubgraphEdge(BaseModel):
    source: str
    target: str
    type: str


class Subgraph(BaseModel):
    """Vizinhança citável para um (classe canônica, STRIDE) — contexto fechado para o LLM."""

    canonical: str
    stride: str
    nodes: list[SubgraphNode] = Field(default_factory=list)
    edges: list[SubgraphEdge] = Field(default_factory=list)

    def ids(self, kind: str) -> list[str]:
        return [n.id for n in self.nodes if n.kind == kind]

    def is_empty(self) -> bool:
        return not self.nodes
