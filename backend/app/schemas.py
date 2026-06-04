"""Schema canônico compartilhado pelos dois sistemas (Cíclope e ARGUS).

A saída de ambos é um `ThreatModel` — é isso que torna a comparação justa
(mesmo contrato de entrada/saída). Ver PLANO-IMPLEMENTACAO.md, Fase 0.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Vocabulários fechados (reduzem alucinação; usados em structured output) ──

StrideCategory = Literal[
    "Spoofing",
    "Tampering",
    "Repudiation",
    "Information Disclosure",
    "Denial of Service",
    "Elevation of Privilege",
]

ElementType = Literal[
    "Process",
    "DataStore",
    "DataFlow",
    "ExternalEntity",
    "TrustBoundary",
]

Likelihood = Literal["High", "Medium", "Low"]
Impact = Literal["Critical", "High", "Medium", "Low"]
MitigationType = Literal["Preventive", "Detective", "Corrective"]
ThreatStatus = Literal["Open", "Mitigated", "Accepted"]
Provenance = Literal["ciclope", "argus"]


# ── Modelos ──

class Mitigation(BaseModel):
    description: str
    type: MitigationType = "Preventive"
    refs: list[str] = Field(
        default_factory=list,
        description="Referências citáveis, ex.: 'ASVS V2.1.1', 'CWE-287', 'D3FEND ...'.",
    )


class Threat(BaseModel):
    id: str = Field(description="Identificador único, ex.: THR-001.")
    component_id: str = Field(description="ID do componente/elemento alvo.")
    element_type: ElementType
    stride_category: StrideCategory
    title: str
    attack_scenario: str = Field(description="Cenário de ataque específico ao componente.")
    likelihood: Likelihood = "Medium"
    impact: Impact = "Medium"
    risk_score: int = Field(default=1, ge=1, le=25, description="Matriz 5x5 (DREAD entra na Fase 3).")
    cwe_ids: list[str] = Field(default_factory=list)
    capec_ids: list[str] = Field(default_factory=list)
    attack_ids: list[str] = Field(default_factory=list)
    mitigations: list[Mitigation] = Field(default_factory=list)
    status: ThreatStatus = "Open"
    provenance: Provenance = "argus"
    grounded: bool = Field(
        default=False,
        description="True se CWE/CAPEC/CVE foram validados contra catálogo (Fase 3/5).",
    )


class Component(BaseModel):
    id: str
    canonical: str = Field(description="Classe canônica (ver taxonomia agnóstica).")
    label: str | None = Field(default=None, description="Rótulo lido do diagrama (OCR/VLM).")
    element_type: ElementType
    bbox: list[float] | None = Field(
        default=None, description="[x, y, w, h] normalizado (quando vem do detector)."
    )
    confidence: float | None = None


class Edge(BaseModel):
    source: str = Field(description="component_id de origem.")
    target: str = Field(description="component_id de destino.")
    label: str | None = None
    crosses_boundary: bool = False


class ThreatModel(BaseModel):
    system_name: str = "Sistema sob análise"
    components: list[Component] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    threats: list[Threat] = Field(default_factory=list)
    meta: dict = Field(
        default_factory=dict,
        description="provider, modelo, latência (s), custo, versões, etc.",
    )
