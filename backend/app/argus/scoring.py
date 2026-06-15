"""E6 — Scoring DREAD determinístico (Damage, Reproducibility, Exploitability, Affected, Discoverability).

A fraqueza histórica do DREAD é a SUBJETIVIDADE (analistas diferentes dão notas diferentes).
Mitigamos isso com **defaults fixos e calibrados por (tipo de elemento DFD × categoria STRIDE)**:
mesma entrada → mesma nota, 100% reprodutível e auditável (e idêntico para Cíclope e ARGUS).
Cada dimensão é 1–10; o score é a **média** (1–10); a faixa de risco vem de limiares fixos.
Mantemos o `risk_score` 5×5 (Prob.×Impacto) como visão executiva — DREAD é a visão granular.
"""

from __future__ import annotations

from app.schemas import Impact, Likelihood, Threat

_DIMS = ("damage", "reproducibility", "exploitability", "affected", "discoverability")

# 5×5 executivo: pesos das bandas (Prob.×Impacto), iguais ao do E4 — mas agora as bandas DERIVAM
# do DREAD (mesma base determinística), então `risk_score` fica coerente com `dread_band`.
_L = {"High": 5, "Medium": 3, "Low": 1}
_I = {"Critical": 5, "High": 4, "Medium": 2, "Low": 1}

# Base DREAD por categoria STRIDE (D, R, E, A, Disc) — calibrada e documentada (ver relatório §5).
_BASE: dict[str, tuple[int, int, int, int, int]] = {
    "Spoofing": (7, 8, 6, 8, 6),                 # personificação: confiável de reproduzir, afeta muitos
    "Tampering": (8, 6, 6, 7, 5),                # integridade: alto dano
    "Repudiation": (4, 6, 5, 4, 5),              # negação de autoria: dano direto menor
    "Information Disclosure": (7, 7, 6, 8, 6),   # vazamento: afeta muitos, frequentemente descobrível
    "Denial of Service": (6, 8, 7, 9, 7),        # indisponibilidade: fácil, afeta todos
    "Elevation of Privilege": (9, 5, 4, 8, 4),   # escalada: dano máximo, porém mais difícil
}

# Modificador (delta) por tipo de elemento DFD — pequenos ajustes ao contexto do alvo.
_ELEM: dict[str, tuple[int, int, int, int, int]] = {
    "DataStore": (1, 0, 0, 1, 0),        # dados valiosos → +Damage +Affected
    "DataFlow": (0, 0, 0, 0, 1),         # observável na rede → +Discoverability
    "ExternalEntity": (-1, 0, -1, 0, 0), # fora do nosso controle → impacto direto menor
    "Process": (0, 0, 0, 0, 0),
    "TrustBoundary": (0, 0, 0, 0, 0),
}


def _band(score: float) -> str:
    if score >= 8:
        return "Crítico"
    if score >= 6:
        return "Alto"
    if score >= 4:
        return "Médio"
    return "Baixo"


def dread(element_type: str, stride_category: str) -> dict:
    """Vetor DREAD determinístico para (elemento, categoria) — dims 1–10, score (média) e faixa."""
    base = _BASE.get(stride_category, (5, 5, 5, 5, 5))
    mod = _ELEM.get(element_type, (0, 0, 0, 0, 0))
    vals = [max(1, min(10, b + m)) for b, m in zip(base, mod, strict=True)]
    score = round(sum(vals) / len(vals), 1)
    out: dict = dict(zip(_DIMS, vals, strict=True))
    out["score"] = score
    out["band"] = _band(score)
    return out


def _likelihood_from(d: dict) -> Likelihood:
    """Probabilidade (5×5) a partir do DREAD: facilidade = Repro+Exploit+Discover."""
    x = (d["reproducibility"] + d["exploitability"] + d["discoverability"]) / 3
    return "High" if x >= 7 else "Medium" if x >= 4.5 else "Low"


def _impact_from(d: dict) -> Impact:
    """Impacto (5×5) a partir do DREAD: severidade = Damage+Affected."""
    x = (d["damage"] + d["affected"]) / 2
    return "Critical" if x >= 8 else "High" if x >= 6 else "Medium" if x >= 4 else "Low"


def apply(threats: list[Threat]) -> None:
    """Anexa DREAD a cada ameaça in-place (determinístico; agnóstico de sistema).

    O `risk_score` 5×5 e os campos `likelihood`/`impact` também passam a DERIVAR do DREAD (mesma
    base), eliminando a contradição que o juiz flagou (ex.: `dread_band` Alto com `risk_score` baixo)
    e tornando a visão executiva igualmente determinística/reprodutível para Cíclope e ARGUS."""
    for t in threats:
        d = dread(t.element_type, t.stride_category)
        t.dread = {k: int(d[k]) for k in _DIMS}
        t.dread_score = float(d["score"])
        t.dread_band = str(d["band"])
        lik, imp = _likelihood_from(d), _impact_from(d)
        t.likelihood, t.impact = lik, imp
        t.risk_score = max(1, min(25, _L[lik] * _I[imp]))


def distribution(threats: list[Threat]) -> dict:
    """Distribuição de risco por faixa DREAD (para o resumo/painel)."""
    out = {"Crítico": 0, "Alto": 0, "Médio": 0, "Baixo": 0}
    for t in threats:
        if t.dread_band in out:
            out[t.dread_band] += 1
    return out
