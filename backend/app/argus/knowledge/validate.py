"""Validação de ancoragem — a RÉGUA do estudo comparativo (agnóstica de sistema).

Recebe ameaças de QUALQUER `ThreatModel` (Cíclope ou ARGUS) e confere cada ID citado
(CWE/CAPEC; CVE/ATT&CK quando os catálogos existirem) contra o `KnowledgeStore`:
  - IDs inexistentes = **alucinação** → opcionalmente removidos das listas estruturadas;
  - `Threat.grounded` = citou ≥1 âncora válida (e, na medição, nenhuma inválida);
  - `ValidationReport` resume groundedness (% de ameaças) e validade de IDs (% de citações reais).

O E5 do ARGUS chama isto com `drop_invalid=True` (limpa); a Fase 5 chama sobre a saída do
Cíclope com `drop_invalid=False` (apenas mede a alucinação do baseline).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.argus.knowledge.store import KnowledgeStore
from app.schemas import Threat, ThreatModel

# Padrões de id reconhecidos em campos de texto livre (ex.: mitigations[].refs).
_ID_RE: dict[str, re.Pattern[str]] = {
    "CWE": re.compile(r"\bCWE-(\d+)\b", re.IGNORECASE),
    "CAPEC": re.compile(r"\bCAPEC-(\d+)\b", re.IGNORECASE),
}


@dataclass
class ValidationReport:
    threats: int = 0
    grounded: int = 0
    ids_total: int = 0
    ids_valid: int = 0
    ids_invalid: int = 0
    invalid: list[str] = field(default_factory=list)
    sem_candidates: int = 0      # candidatos sugeridos pela busca semântica (Chroma)
    threats_semantic: int = 0    # ameaças com ≥1 âncora vinda só do semântico

    @property
    def groundedness(self) -> float:
        return round(self.grounded / self.threats, 3) if self.threats else 0.0

    @property
    def id_validity(self) -> float:
        return round(self.ids_valid / self.ids_total, 3) if self.ids_total else 0.0

    def as_meta(self) -> dict:
        return {
            "groundedness": self.groundedness,
            "id_validity": self.id_validity,
            "ids_valid": self.ids_valid,
            "ids_invalid": self.ids_invalid,
            "threats_grounded": self.grounded,
            "threats_total": self.threats,
            "sem_candidates": self.sem_candidates,
            "threats_semantic": self.threats_semantic,
        }


def _norm(raw: str, kind: str) -> str:
    s = raw.strip().upper()
    if s.startswith(f"{kind}-"):
        return s
    digits = re.sub(r"\D", "", s)
    return f"{kind}-{digits}" if digits else s


def _cited(threat: Threat) -> list[tuple[str, str]]:
    """Pares (kind, id) citados pela ameaça: listas estruturadas + refs de texto livre."""
    out: list[tuple[str, str]] = []
    for c in threat.cwe_ids:
        out.append(("CWE", _norm(c, "CWE")))
    for c in threat.capec_ids:
        out.append(("CAPEC", _norm(c, "CAPEC")))
    for c in threat.attack_ids:  # ATT&CK: id já vem como 'T1078' (sem normalização numérica)
        out.append(("ATTACK", c.strip().upper()))
    for m in threat.mitigations:
        for ref in m.refs:
            for kind, rx in _ID_RE.items():
                for num in rx.findall(ref):
                    out.append((kind, f"{kind}-{num}"))
    # dedup preservando ordem
    seen: set[tuple[str, str]] = set()
    uniq: list[tuple[str, str]] = []
    for pair in out:
        if pair not in seen:
            seen.add(pair)
            uniq.append(pair)
    return uniq


def _present_kinds(store: KnowledgeStore) -> set[str]:
    """Tipos de nó presentes no store (só validamos o que há catálogo p/ validar)."""
    return {e.kind for e in store.iter_entities()}


def validate_threats(
    threats: list[Threat], store: KnowledgeStore, *, drop_invalid: bool = True
) -> ValidationReport:
    """Valida as âncoras de cada ameaça (in-place: `grounded` e, se `drop_invalid`, remove IDs falsos)."""
    present = _present_kinds(store)
    rep = ValidationReport()
    for t in threats:
        rep.threats += 1
        valid_here = invalid_here = 0
        for kind, cid in _cited(t):
            if kind not in present:  # catálogo ainda não ingerido → não conta (evita falso-inválido)
                continue
            rep.ids_total += 1
            if store.exists(kind, cid):
                rep.ids_valid += 1
                valid_here += 1
            else:
                rep.ids_invalid += 1
                invalid_here += 1
                if len(rep.invalid) < 50:
                    rep.invalid.append(cid)
        if drop_invalid:
            t.cwe_ids = [c for c in t.cwe_ids if "CWE" not in present or store.exists("CWE", _norm(c, "CWE"))]
            t.capec_ids = [c for c in t.capec_ids if "CAPEC" not in present or store.exists("CAPEC", _norm(c, "CAPEC"))]
            t.attack_ids = [c for c in t.attack_ids if "ATTACK" not in present or store.exists("ATTACK", c.strip().upper())]
            t.grounded = valid_here > 0
        else:
            t.grounded = valid_here > 0 and invalid_here == 0
        rep.grounded += int(t.grounded)
    return rep


def validate_model(tm: ThreatModel, store: KnowledgeStore, *, drop_invalid: bool = True) -> ValidationReport:
    """Conveniência: valida `tm.threats` e grava o resumo em `tm.meta`."""
    rep = validate_threats(tm.threats, store, drop_invalid=drop_invalid)
    tm.meta.update(rep.as_meta())
    return rep
