"""Renderização do relatório STRIDE: ThreatModel → HTML (Jinja2) → PDF (WeasyPrint).

Mínimo da Fase 0; a estrutura completa (Shostack 4-perguntas, DFD, checklist)
é polida na Fase 4.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.schemas import ThreatModel

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


def _group_by_category(tm: ThreatModel) -> dict[str, list]:
    groups: dict[str, list] = {cat: [] for cat in _STRIDE_ORDER}
    for threat in tm.threats:
        groups.setdefault(threat.stride_category, []).append(threat)
    return groups


def to_html(tm: ThreatModel) -> str:
    template = _env.get_template("report.html.j2")
    return template.render(tm=tm, groups=_group_by_category(tm), sev_class=_sev_class)


def to_pdf(tm: ThreatModel) -> bytes:
    # Import tardio: isola dependências nativas (cairo/pango) do carregamento do app.
    from weasyprint import HTML

    return HTML(string=to_html(tm)).write_pdf()
