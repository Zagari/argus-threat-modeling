"""E5 — Enriquecimento ancorado (híbrido: determinístico ∪ semântico) + validação.

Para cada `Threat`, os candidatos vêm do subgrafo `(classe, STRIDE)` (determinístico) UNIDOS aos
mais relevantes da **busca semântica** (Chroma, quando pronta). O LLM seleciona apenas entre os
candidatos. Rastreamos a **procedência**: âncoras que vieram SÓ do semântico (e não do mapeamento
curado) ficam em `Threat.semantic_anchors`. Em mock/erro/sem-RAG, cai no determinístico (grounded).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from app.argus.knowledge import rag, validate
from app.argus.knowledge.model import Subgraph
from app.argus.knowledge.store import KnowledgeStore
from app.config import get_config
from app.llm import provider
from app.schemas import Component, Mitigation, Threat

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "llm" / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR), autoescape=select_autoescape(disabled_extensions=("j2",)))

_SYSTEM = "Você ancora ameaças STRIDE em CWE/CAPEC/ATT&CK/ASVS reais. Cite APENAS os IDs candidatos fornecidos."
_MAX_CWE = 3
_MAX_CAPEC = 2
_MAX_ATTACK = 2
_SEM_CWE = 3
_SEM_CAPEC = 2


class _EnrichItem(BaseModel):
    threat_id: str
    cwe_ids: list[str] = Field(default_factory=list)
    capec_ids: list[str] = Field(default_factory=list)
    attack_ids: list[str] = Field(default_factory=list)
    mitigations: list[Mitigation] = Field(default_factory=list)


class _EnrichResponse(BaseModel):
    items: list[_EnrichItem] = Field(default_factory=list)


class _Pair:
    """Estado por ameaça: subgrafo determinístico + hits semânticos + pools de candidatos."""

    def __init__(self, threat: Threat, sg: Subgraph, sem: dict[str, str]) -> None:
        self.t = threat
        self.sg = sg
        self.sem = sem  # id -> name (só do semântico)
        self.cwe = {n.id: n.name for n in sg.nodes if n.kind == "CWE"}
        self.capec = {n.id: n.name for n in sg.nodes if n.kind == "CAPEC"}
        for sid, sname in sem.items():
            if sid.startswith("CWE-"):
                self.cwe.setdefault(sid, sname)
            elif sid.startswith("CAPEC-"):
                self.capec.setdefault(sid, sname)
        self.attack = {n.id: n.name for n in sg.nodes if n.kind == "ATTACK"}
        self.controls = {n.id: n.name for n in sg.nodes if n.kind in ("Control", "D3FEND")}


def _semantic_hits(threat: Threat) -> dict[str, str]:
    if not rag.ready():
        return {}
    q = f"{threat.title}. {threat.attack_scenario}"
    hits = rag.search(q, kind="CWE", k=_SEM_CWE) + rag.search(q, kind="CAPEC", k=_SEM_CAPEC)
    return {h["id"]: h["name"] for h in hits}


def _apply_deterministic(p: _Pair) -> None:
    """Fallback: anexa os candidatos do subgrafo (todos reais → grounded)."""
    t, sg = p.t, p.sg
    t.cwe_ids = sg.ids("CWE")[:_MAX_CWE]
    t.capec_ids = sg.ids("CAPEC")[:_MAX_CAPEC]
    t.attack_ids = sg.ids("ATTACK")[:_MAX_ATTACK]
    controls = [(n.id, n.name) for n in sg.nodes if n.kind == "Control" and "." not in n.id]
    if controls and not any(m.refs for m in t.mitigations):
        names = ", ".join(name for _, name in controls)
        t.mitigations.append(
            Mitigation(description=f"Aplicar os controles de {names}.", type="Preventive",
                       refs=[cid for cid, _ in controls])
        )


_ANCHOR_RE = re.compile(r"^(CWE-\d+|CAPEC-\d+|T\d{4}(?:\.\d+)?)$", re.IGNORECASE)


def _ref_ok(ref: str, allowed: set[str]) -> bool:
    """Mantém controles (ASVS/NIST/D3FEND) e descrições; descarta âncora CWE/CAPEC/ATT&CK que NÃO
    esteja entre os candidatos — anti-vazamento de id alucinado no texto da contramedida (3.x)."""
    s = ref.strip().upper()
    return s in allowed if _ANCHOR_RE.match(s) else True


def _apply_item(p: _Pair, item: _EnrichItem) -> None:
    """Aplica a seleção do LLM, filtrando para os candidatos (det ∪ semântico)."""
    p.t.cwe_ids = [c for c in item.cwe_ids if c in p.cwe][:_MAX_CWE]
    p.t.capec_ids = [c for c in item.capec_ids if c in p.capec][:_MAX_CAPEC]
    p.t.attack_ids = [a for a in item.attack_ids if a in p.attack][:_MAX_ATTACK]
    if item.mitigations:
        allowed = {x.upper() for x in (*p.cwe, *p.capec, *p.attack)}  # candidatos (chaves)
        for m in item.mitigations:
            m.refs = [r for r in m.refs if _ref_ok(r, allowed)]
        p.t.mitigations = item.mitigations


def enrich(threats: list[Threat], components: list[Component], store: KnowledgeStore) -> validate.ValidationReport:
    """Enriquece e valida as ameaças in-place; devolve o `ValidationReport` (groundedness + semântico)."""
    canon = {c.id: c.canonical for c in components}
    pairs = [_Pair(t, store.subgraph(canon.get(t.component_id, ""), t.stride_category), _semantic_hits(t)) for t in threats]
    sem_total = sum(len(p.sem) for p in pairs)

    if get_config().mock:
        for p in pairs:
            _apply_deterministic(p)
    else:
        try:
            _enrich_via_llm(pairs)
        except Exception:  # noqa: BLE001 — E5 é reforço; nunca derruba o pipeline
            for p in pairs:
                _apply_deterministic(p)

    for p in pairs:
        if not p.t.cwe_ids and p.sg.ids("CWE"):
            _apply_deterministic(p)
        det = set(p.sg.ids("CWE")) | set(p.sg.ids("CAPEC"))  # procedência: só-semântico = no hit e fora do det
        p.t.semantic_anchors = [c for c in (p.t.cwe_ids + p.t.capec_ids) if c in p.sem and c not in det]

    report = validate.validate_threats(threats, store, drop_invalid=True)
    report.sem_candidates = sem_total
    report.threats_semantic = sum(1 for t in threats if t.semantic_anchors)
    return report


def _enrich_via_llm(pairs: list[_Pair]) -> None:
    items = [
        {
            "threat_id": p.t.id, "stride": p.t.stride_category, "title": p.t.title, "scenario": p.t.attack_scenario,
            "candidates": {
                "cwe": [{"id": i, "name": n} for i, n in p.cwe.items()],
                "capec": [{"id": i, "name": n} for i, n in p.capec.items()],
                "attack": [{"id": i, "name": n} for i, n in p.attack.items()],
                "controls": [{"id": i, "name": n} for i, n in p.controls.items()],
            },
        }
        for p in pairs
    ]
    prompt = _env.get_template("enrich.j2").render() + "\n\nITENS:\n" + json.dumps(items, ensure_ascii=False)
    resp = provider.chat(
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
        response_model=_EnrichResponse,
        temperature=0.1,
    )
    by_id = {it.threat_id: it for it in resp.items}  # type: ignore[union-attr]
    for p in pairs:
        item = by_id.get(p.t.id)
        if item is not None:
            _apply_item(p, item)
