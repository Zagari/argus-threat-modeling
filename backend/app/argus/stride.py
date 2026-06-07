"""E4 — STRIDE-per-element.

Gera as ameaças do `ThreatModel` a partir do DFD (E3). O diferencial em relação ao Cíclope
é a \\textbf{matriz STRIDE-per-element}: para cada elemento, o LLM é instruído a propor
ameaças SÓ nas categorias aplicáveis ao seu tipo DFD, e um \\textbf{filtro determinístico}
descarta qualquer categoria fora da matriz (`app.taxonomy.applicable_categories`). O foco
recai nos fluxos que cruzam fronteira de confiança (marcados no E3).

A pontuação inicial é uma matriz 5x5 (likelihood x impact); DREAD entra na Fase 3. As
ameaças saem com `grounded=False` --- a validação em CWE/CAPEC/CVE é o E5.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.config import get_config
from app.llm import provider
from app.schemas import Component, Edge, Impact, Likelihood, Mitigation, StrideCategory, Threat
from app.taxonomy import applicable_categories

_SYSTEM = (
    "Você é um especialista em segurança de software com mais de 20 anos aplicando a "
    "metodologia STRIDE a arquiteturas de nuvem. Gera ameaças específicas, acionáveis e "
    "ancoradas no componente. Responda sempre em português."
)

_PROMPT = """A partir do Data Flow Diagram (DFD) abaixo, gere as ameaças STRIDE.

Componentes (id | classe | tipo DFD | rótulo | categorias STRIDE PERMITIDAS):
{components}

Fluxos (origem -> destino | cruza fronteira de confiança?):
{edges}

Regras OBRIGATÓRIAS:
- Para cada componente, gere ameaças SOMENTE nas categorias listadas como permitidas para ele.
- PRIORIZE os componentes envolvidos em fluxos que CRUZAM fronteira de confiança.
- Cada ameaça deve ser ESPECÍFICA ao componente (cite a classe/rótulo e o cenário de ataque),
  não genérica.
- Informe `likelihood` (High/Medium/Low), `impact` (Critical/High/Medium/Low), `cwe_ids`
  sugeridos (ex.: "CWE-89") e UMA mitigação por ameaça.
- Use os ids EXATOS dos componentes em `component_id`."""

_L = {"High": 5, "Medium": 3, "Low": 1}
_I = {"Critical": 5, "High": 4, "Medium": 2, "Low": 1}


class _ThreatGen(BaseModel):
    component_id: str
    stride_category: StrideCategory
    title: str
    attack_scenario: str
    likelihood: Likelihood = "Medium"
    impact: Impact = "Medium"
    cwe_ids: list[str] = Field(default_factory=list)
    mitigation: str = ""


class _Gen(BaseModel):
    threats: list[_ThreatGen] = Field(default_factory=list)


def _score(likelihood: str, impact: str) -> int:
    return max(1, min(25, _L.get(likelihood, 3) * _I.get(impact, 2)))


def _mock_threats(components: list[Component]) -> list[Threat]:
    """Sem LLM: uma ameaça por componente, na PRIMEIRA categoria permitida (exercita a matriz)."""
    out: list[Threat] = []
    for c in components:
        cats = applicable_categories(c.element_type)
        if not cats:
            continue
        out.append(Threat(
            id=f"THR-{len(out) + 1:03d}", component_id=c.id, element_type=c.element_type,
            stride_category=cats[0],  # type: ignore[arg-type]  # valor da matriz é StrideCategory
            title=f"Ameaça {cats[0]} em {c.canonical}",
            attack_scenario=f"Cenário mock de {cats[0]} no componente {c.label or c.canonical}.",
            risk_score=_score("Medium", "Medium"), provenance="argus", grounded=False,
        ))
    return out


def generate(components: list[Component], edges: list[Edge]) -> list[Threat]:
    """DFD → lista de ameaças STRIDE (constrangidas pela matriz por elemento)."""
    flow_comps = [c for c in components if c.element_type != "TrustBoundary"]
    if not flow_comps:
        return []

    cfg = get_config()
    if cfg.mock:
        return _mock_threats(flow_comps)

    by_id = {c.id: c for c in flow_comps}
    comp_lines = "\n".join(
        f"- {c.id} | {c.canonical} | {c.element_type} | {c.label or '-'} | "
        f"{', '.join(applicable_categories(c.element_type))}"
        for c in flow_comps
    )
    edge_lines = "\n".join(
        f"- {e.source} -> {e.target} | {'sim' if e.crosses_boundary else 'não'}"
        for e in edges
    ) or "(sem fluxos)"
    prompt = _PROMPT.format(components=comp_lines, edges=edge_lines)
    gen: _Gen = provider.chat(  # type: ignore[assignment]
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
        response_model=_Gen, temperature=0.2,
    )

    threats: list[Threat] = []
    for g in gen.threats:
        comp = by_id.get(g.component_id)
        if comp is None:
            continue
        # filtro determinístico: descarta categoria fora da matriz do elemento
        if g.stride_category not in applicable_categories(comp.element_type):
            continue
        mitigations = [Mitigation(description=g.mitigation)] if g.mitigation.strip() else []
        threats.append(Threat(
            id=f"THR-{len(threats) + 1:03d}", component_id=g.component_id,
            element_type=comp.element_type, stride_category=g.stride_category,
            title=g.title, attack_scenario=g.attack_scenario,
            likelihood=g.likelihood, impact=g.impact,
            risk_score=_score(g.likelihood, g.impact),
            cwe_ids=g.cwe_ids, mitigations=mitigations,
            provenance="argus", grounded=False,
        ))
    return threats
