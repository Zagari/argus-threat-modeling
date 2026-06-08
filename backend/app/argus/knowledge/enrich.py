"""E5 — Enriquecimento ancorado: preenche CWE/CAPEC/contramedidas citando só o recuperado.

Para cada `Threat`, recupera o subgrafo citável `(classe canônica, STRIDE)` do `KnowledgeStore`
e pede ao LLM que **selecione apenas entre os candidatos** (recuperação fechada → menos
alucinação na origem). Em modo mock ou em falha do LLM, cai num **fallback determinístico**
(anexa os candidatos do subgrafo). Ao final, `validate_threats(drop_invalid=True)` remove qualquer
ID que escape e marca `grounded`. É o estágio exclusivo do ARGUS (o Cíclope não tem retrieval).
"""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from app.argus.knowledge import validate
from app.argus.knowledge.model import Subgraph
from app.argus.knowledge.store import KnowledgeStore
from app.config import get_config
from app.llm import provider
from app.schemas import Component, Mitigation, Threat

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "llm" / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR), autoescape=select_autoescape(disabled_extensions=("j2",)))

_SYSTEM = "Você ancora ameaças STRIDE em CWE/CAPEC/ASVS reais. Cite APENAS os IDs candidatos fornecidos."
_MAX_CWE = 3
_MAX_CAPEC = 2


class _EnrichItem(BaseModel):
    threat_id: str
    cwe_ids: list[str] = Field(default_factory=list)
    capec_ids: list[str] = Field(default_factory=list)
    mitigations: list[Mitigation] = Field(default_factory=list)


class _EnrichResponse(BaseModel):
    items: list[_EnrichItem] = Field(default_factory=list)


def _candidates(sg: Subgraph) -> dict:
    return {
        "cwe": [{"id": n.id, "name": n.name} for n in sg.nodes if n.kind == "CWE"],
        "capec": [{"id": n.id, "name": n.name} for n in sg.nodes if n.kind == "CAPEC"],
        "controls": [{"id": n.id, "name": n.name} for n in sg.nodes if n.kind == "Control"],
    }


def _apply_deterministic(threat: Threat, sg: Subgraph) -> None:
    """Fallback: anexa os candidatos do subgrafo (todos reais → grounded)."""
    threat.cwe_ids = sg.ids("CWE")[:_MAX_CWE]
    threat.capec_ids = sg.ids("CAPEC")[:_MAX_CAPEC]
    controls = [(n.id, n.name) for n in sg.nodes if n.kind == "Control"]
    if controls and not any(m.refs for m in threat.mitigations):
        names = ", ".join(name for _, name in controls)
        threat.mitigations.append(
            Mitigation(description=f"Aplicar os controles de {names}.", type="Preventive",
                       refs=[cid for cid, _ in controls])
        )


def _apply_item(threat: Threat, item: _EnrichItem, sg: Subgraph) -> None:
    """Aplica a seleção do LLM, filtrando para os candidatos (segurança extra)."""
    cand_cwe = set(sg.ids("CWE"))
    cand_capec = set(sg.ids("CAPEC"))
    threat.cwe_ids = [c for c in item.cwe_ids if c in cand_cwe][:_MAX_CWE]
    threat.capec_ids = [c for c in item.capec_ids if c in cand_capec][:_MAX_CAPEC]
    if item.mitigations:
        threat.mitigations = item.mitigations


def enrich(threats: list[Threat], components: list[Component], store: KnowledgeStore) -> validate.ValidationReport:
    """Enriquece e valida as ameaças in-place; devolve o `ValidationReport` (groundedness)."""
    canon = {c.id: c.canonical for c in components}
    pairs: list[tuple[Threat, Subgraph]] = [
        (t, store.subgraph(canon.get(t.component_id, ""), t.stride_category)) for t in threats
    ]

    if get_config().mock:
        for t, sg in pairs:
            _apply_deterministic(t, sg)
    else:
        try:
            _enrich_via_llm(pairs)
        except Exception:  # noqa: BLE001 — E5 é reforço; nunca derruba o pipeline
            for t, sg in pairs:
                _apply_deterministic(t, sg)

    # Garante âncora onde o LLM não retornou nada mas há candidatos.
    for t, sg in pairs:
        if not t.cwe_ids and sg.ids("CWE"):
            _apply_deterministic(t, sg)

    return validate.validate_threats(threats, store, drop_invalid=True)


def _enrich_via_llm(pairs: list[tuple[Threat, Subgraph]]) -> None:
    items = [
        {
            "threat_id": t.id,
            "stride": t.stride_category,
            "title": t.title,
            "scenario": t.attack_scenario,
            "candidates": _candidates(sg),
        }
        for t, sg in pairs
    ]
    prompt = _env.get_template("enrich.j2").render() + "\n\nITENS:\n" + json.dumps(items, ensure_ascii=False)
    resp = provider.chat(
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
        response_model=_EnrichResponse,
        temperature=0.1,
    )
    by_id = {it.threat_id: it for it in resp.items}  # type: ignore[union-attr]
    for t, sg in pairs:
        item = by_id.get(t.id)
        if item is not None:
            _apply_item(t, item, sg)
