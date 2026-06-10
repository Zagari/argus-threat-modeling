"""Renderização do relatório STRIDE: ThreatModel → HTML (Jinja2) → PDF (WeasyPrint).

Mínimo da Fase 0; a estrutura completa (Shostack 4-perguntas, DFD, checklist)
é polida na Fase 4.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.schemas import ThreatModel

# Matriz STRIDE-per-element (qual categoria se aplica a cada tipo) — base do checklist de cobertura.
_STRIDE_MATRIX: dict[str, set[str]] = {
    "ExternalEntity": {"Spoofing", "Repudiation"},
    "Process": {"Spoofing", "Tampering", "Repudiation", "Information Disclosure", "Denial of Service", "Elevation of Privilege"},
    "DataStore": {"Tampering", "Repudiation", "Information Disclosure", "Denial of Service"},
    "DataFlow": {"Tampering", "Information Disclosure", "Denial of Service"},
}

_STRIDE_ORDER = [
    "Spoofing",
    "Tampering",
    "Repudiation",
    "Information Disclosure",
    "Denial of Service",
    "Elevation of Privilege",
]

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=select_autoescape(["html", "xml"]))


def _sev_class(impact: str) -> str:
    return {"Critical": "crit", "High": "high", "Medium": "med", "Low": "low"}.get(impact, "low")


def cite_url(cid: str) -> str | None:
    """URL oficial da fonte para um id de catálogo (CWE/CAPEC/ATT&CK/CVE/ASVS); espelha o front."""
    s = (cid or "").strip().upper()
    if m := re.match(r"^CWE-(\d+)$", s):
        return f"https://cwe.mitre.org/data/definitions/{m.group(1)}.html"
    if m := re.match(r"^CAPEC-(\d+)$", s):
        return f"https://capec.mitre.org/data/definitions/{m.group(1)}.html"
    if re.match(r"^CVE-\d{4}-\d+$", s):
        return f"https://nvd.nist.gov/vuln/detail/{s}"
    if m := re.match(r"^(T\d{4})(?:\.(\d+))?$", s):
        sub = m.group(2)
        return f"https://attack.mitre.org/techniques/{m.group(1)}/{sub}/" if sub else f"https://attack.mitre.org/techniques/{m.group(1)}/"
    if s.startswith("NIST-"):
        from app.argus.knowledge.seeds import nist_url

        return nist_url(s)
    if s.startswith("D3F-"):
        return f"https://d3fend.mitre.org/technique/d3f:{cid.strip()[4:]}/"
    if s.startswith("ASVS"):
        from app.argus.knowledge.seeds import asvs_url

        return asvs_url(s)
    return None


def _dread_band_class(band: str | None) -> str:
    return {"Crítico": "crit", "Alto": "high", "Médio": "med", "Baixo": "low"}.get(band or "", "low")


def _is_control(ref: str) -> bool:
    """True se o ref é contramedida (ASVS/NIST/D3FEND) — vs âncora ofensiva (CWE/CAPEC/CVE/ATT&CK)."""
    s = (ref or "").strip().upper()
    return s.startswith("ASVS") or s.startswith("NIST-") or s.startswith("D3F-")


_env.tests["control"] = _is_control


def _group_by_category(tm: ThreatModel) -> dict[str, list]:
    groups: dict[str, list] = {cat: [] for cat in _STRIDE_ORDER}
    for threat in tm.threats:
        groups.setdefault(threat.stride_category, []).append(threat)
    return groups


def _top_risks(tm: ThreatModel, n: int = 12) -> list:
    """Ameaças ordenadas por risco (DREAD primeiro, depois a matriz 5×5) — visão de priorização."""
    return sorted(
        tm.threats,
        key=lambda t: (t.dread_score if t.dread_score is not None else 0.0, t.risk_score),
        reverse=True,
    )[:n]


def _cited_controls(tm: ThreatModel) -> list[str]:
    """Contramedidas (ASVS/NIST/D3FEND) citadas em todas as ameaças, sem repetição — checklist de ação."""
    seen: dict[str, None] = {}
    for t in tm.threats:
        for m in t.mitigations:
            for ref in m.refs:
                if _is_control(ref):
                    seen.setdefault(ref, None)
    return sorted(seen)


def _coverage(tm: ThreatModel) -> dict:
    """Checklist da 4ª pergunta de Shostack ('fizemos um bom trabalho?') a partir dos dados disponíveis."""
    covered: dict[str, set[str]] = {}
    for t in tm.threats:
        covered.setdefault(t.component_id, set()).add(t.stride_category)

    analyzed = [c for c in tm.components if c.element_type in _STRIDE_MATRIX]
    gaps: list[tuple[str, list[str]]] = []
    for c in analyzed:
        missing = sorted(_STRIDE_MATRIX[c.element_type] - covered.get(c.id, set()))
        if missing:
            gaps.append((c.label or c.id, missing))
    full = len(analyzed) - len(gaps)

    n = len(tm.threats)
    dread_ok = sum(1 for t in tm.threats if t.dread_score is not None)
    crossing = tm.meta.get("crossing_flows")
    if crossing is None:
        crossing = sum(1 for e in tm.edges if e.crosses_boundary)
    g = tm.meta.get("groundedness")

    checks = [
        {"label": "Cobertura STRIDE-per-element", "status": "ok" if not gaps else "warn",
         "detail": f"{full}/{len(analyzed)} elementos com todas as categorias aplicáveis cobertas"},
        {"label": "Fluxos que cruzam fronteira", "status": "info",
         "detail": f"{crossing} fluxo(s) atravessam fronteira de confiança (pontos prioritários de S/T/I)"},
        {"label": "Pontuação DREAD", "status": "ok" if n and dread_ok == n else "warn",
         "detail": f"{dread_ok}/{n} ameaças com risco DREAD calculado"},
        {"label": "Groundedness (anti-alucinação)", "status": "ok" if (g or 0) >= 0.8 else "warn",
         "detail": (f"{round(g * 100)}% das ameaças ancoradas em catálogos reais" if g is not None else "não medido")},
        {"label": "CVEs reais (NVD)", "status": "info",
         "detail": f"{tm.meta.get('n_cves', 0)} CVE(s) recuperados dos catálogos (não inventados)"},
    ]
    return {"checks": checks, "gaps": gaps}


def to_html(tm: ThreatModel) -> str:
    template = _env.get_template("report.html.j2")
    return template.render(
        tm=tm,
        groups=_group_by_category(tm),
        top_risks=_top_risks(tm),
        controls=_cited_controls(tm),
        coverage=_coverage(tm),
        gerado_em=datetime.now().strftime("%d/%m/%Y"),
        sev_class=_sev_class,
        cite_url=cite_url,
        dread_band_class=_dread_band_class,
    )


def to_pdf(tm: ThreatModel) -> bytes:
    # Import tardio: isola dependências nativas (cairo/pango) do carregamento do app.
    from weasyprint import HTML

    return HTML(string=to_html(tm)).write_pdf()
