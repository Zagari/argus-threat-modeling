"""E4 — STRIDE-per-element.

Gera as ameaças do `ThreatModel` a partir do DFD (E3). O diferencial em relação ao Cíclope é
tratar a **matriz STRIDE-per-element como GERADOR, não como filtro**: cada célula
`(componente × categoria STRIDE aplicável)` deve ter ≥1 ameaça (cobertura SISTEMÁTICA — é o que
"cem olhos" significa). O LLM gera; um **piso determinístico** (`app.taxonomy.applicable_categories`)
calcula as células faltantes e dispara uma 2ª passada dirigida só a elas (mesmo padrão do cross-check
do E2, que propõe componentes faltantes). O foco extra recai nos fluxos que cruzam fronteira (E3).

A pontuação inicial é uma matriz 5x5 (likelihood x impact); o DREAD (E6) a substitui. As
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

_PROMPT = """A partir do diagrama de arquitetura (a IMAGEM, quando fornecida) e do Data Flow Diagram
(DFD) abaixo, gere as ameaças STRIDE. Use a imagem para contextualizar cada ameaça ao componente
REAL (nome exibido, vizinhança, o que entra/sai dele).

Componentes (id | classe | tipo DFD | rótulo | categorias STRIDE PERMITIDAS):
{components}

Fluxos (origem -> destino | cruza fronteira de confiança?):
{edges}

Regras OBRIGATÓRIAS:
- COBERTURA SISTEMÁTICA (regra central): para CADA componente, gere ao menos UMA ameaça para CADA
  categoria STRIDE listada como permitida — **não pule nenhuma célula da matriz**. NÃO use categorias
  fora da lista permitida de cada componente. Componentes com mais categorias (ex.: Process tem 6)
  geram mais ameaças. Se uma categoria parecer menos óbvia para aquele componente, descreva ainda
  assim o vetor mais plausível (a aplicabilidade já foi pré-filtrada).
- PRIORIZE (severidade maior) os componentes em fluxos que CRUZAM fronteira de confiança.
- `attack_scenario` deve ser ESPECÍFICO e CONTEXTUAL, NUNCA genérico (nada que sirva a qualquer
  sistema). Cite: o RÓTULO/classe do componente, o FLUXO concreto (origem->destino) e a FRONTEIRA
  cruzada quando houver; descreva o PASSO do atacante e o IMPACTO concreto (qual dado/função é
  comprometido). Ex. ruim: "Um atacante pode adulterar os dados." Ex. bom: "Um atacante na rede
  pública intercepta o fluxo 'API Gateway'->'RDS' (cruza a fronteira) e injeta SQL via parâmetro
  não validado, lendo/alterando a tabela de pedidos."
- `title` curto e específico (ex.: "SQL injection no RDS via API Gateway").
- `mitigation`: UMA contramedida CONCRETA e implementável que neutralize ESSE cenário no componente
  citado (não um controle genérico solto).
- Informe `likelihood` (High/Medium/Low), `impact` (Critical/High/Medium/Low) e `cwe_ids` sugeridos
  (ex.: "CWE-89"). Use os ids EXATOS dos componentes em `component_id`."""

_MISSING_PROMPT = """As células (componente × categoria STRIDE) abaixo FALTARAM na 1ª passada da
matriz STRIDE-per-element. Gere UMA ameaça ESPECÍFICA e contextual para CADA célula listada — não
pule nenhuma. Mesmas regras de qualidade: cite rótulo/classe, fluxo concreto, fronteira cruzada, passo
do atacante e impacto; `mitigation` concreta; `cwe_ids`; `component_id` e `stride_category` EXATOS.

Use a IMAGEM (quando houver) e o DFD para contextualizar.
{context}

Células FALTANTES (id | classe | tipo DFD | rótulo | categorias a cobrir):
{cells}"""

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


def _to_threats(
    gens: list[_ThreatGen], by_id: dict[str, Component], start: int,
    only_cells: set[tuple[str, str]] | None = None,
) -> list[Threat]:
    """Converte `_ThreatGen` → `Threat` (filtro determinístico da matriz; numera a partir de `start`+1).
    Se `only_cells`, mantém só ameaças dessas células `(componente, categoria)` — usado no backstop."""
    out: list[Threat] = []
    for g in gens:
        comp = by_id.get(g.component_id)
        if comp is None or g.stride_category not in applicable_categories(comp.element_type):
            continue
        if only_cells is not None and (g.component_id, str(g.stride_category)) not in only_cells:
            continue
        mitigations = [Mitigation(description=g.mitigation)] if g.mitigation.strip() else []
        out.append(Threat(
            id=f"THR-{start + len(out) + 1:03d}", component_id=g.component_id,
            element_type=comp.element_type, stride_category=g.stride_category,
            title=g.title, attack_scenario=g.attack_scenario,
            likelihood=g.likelihood, impact=g.impact, risk_score=_score(g.likelihood, g.impact),
            cwe_ids=g.cwe_ids, mitigations=mitigations, provenance="argus", grounded=False,
        ))
    return out


def _complete_missing(
    missing: set[tuple[str, str]], by_id: dict[str, Component], context: str,
    image_bytes: bytes | None, mime: str,
) -> _Gen:
    """2ª passada (backstop) dirigida às células faltantes — garante o piso da matriz."""
    by_comp: dict[str, list[str]] = {}
    for cid, cat in missing:
        by_comp.setdefault(cid, []).append(cat)
    cells = "\n".join(
        f"- {cid} | {by_id[cid].canonical} | {by_id[cid].element_type} | {by_id[cid].label or '-'} | "
        f"{', '.join(sorted(cats))}"
        for cid, cats in sorted(by_comp.items())
    )
    prompt = _MISSING_PROMPT.format(context=context, cells=cells)
    if image_bytes is not None:
        return provider.vision(  # type: ignore[return-value]
            image_bytes, prompt, response_model=_Gen, mime=mime, system=_SYSTEM, temperature=0.2)
    return provider.chat(  # type: ignore[return-value]
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
        response_model=_Gen, temperature=0.2)


def generate(
    components: list[Component],
    edges: list[Edge],
    *,
    image_bytes: bytes | None = None,
    mime: str = "image/jpeg",
) -> list[Threat]:
    """DFD → lista de ameaças STRIDE (constrangidas pela matriz por elemento).

    Quando `image_bytes` é fornecido, a geração é **multimodal** (o VLM vê o diagrama) — cenários
    mais específicos/contextuais. Sem imagem, cai no caminho texto (DFD apenas)."""
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
    context = f"Componentes:\n{comp_lines}\n\nFluxos:\n{edge_lines}"
    prompt = _PROMPT.format(components=comp_lines, edges=edge_lines)
    if image_bytes is not None:
        gen: _Gen = provider.vision(  # type: ignore[assignment]
            image_bytes, prompt, response_model=_Gen, mime=mime, system=_SYSTEM, temperature=0.2,
        )
    else:
        gen = provider.chat(  # type: ignore[assignment]
            [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
            response_model=_Gen, temperature=0.2,
        )
    threats = _to_threats(gen.threats, by_id, 0)

    # Piso determinístico da matriz: completa as células (componente × categoria aplicável) faltantes.
    required = {(c.id, str(cat)) for c in flow_comps for cat in applicable_categories(c.element_type)}
    missing = required - {(t.component_id, str(t.stride_category)) for t in threats}
    if missing:
        try:
            gen2 = _complete_missing(missing, by_id, context, image_bytes, mime)
            threats += _to_threats(gen2.threats, by_id, len(threats), only_cells=missing)
        except Exception:  # noqa: BLE001 — backstop é reforço; nunca derruba o E4
            pass
    return threats
