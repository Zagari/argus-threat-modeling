"""Requisitos ASVS detalhados (3.6a) — ingest validável + subgrafo + deep-link."""

from __future__ import annotations

from app.argus.knowledge.store import LocalKG
from app.report.render import cite_url


def test_requisitos_asvs_carregados_e_validaveis():
    kg = LocalKG()
    assert kg.exists("Control", "ASVS-V2.1.1") is True   # requisito fino
    assert kg.exists("Control", "ASVS-V2") is True        # capítulo (semente)
    assert kg.exists("Control", "ASVS-V99.9.9") is False
    n_control = sum(1 for e in kg.iter_entities() if e.kind == "Control")
    assert n_control >= 250
    e = kg.entity("Control", "ASVS-V2.1.1")
    assert e and e.name and "github.com/OWASP/ASVS" in (e.url or "")


def test_subgraph_inclui_requisitos_finos():
    controls = LocalKG().subgraph("api_gateway", "Spoofing").ids("Control")
    assert "ASVS-V2" in controls                 # o capítulo (Authentication)
    assert any("." in c for c in controls)       # e ao menos um requisito fino (ASVS-V2.x.y)


def test_cite_url_asvs_deep_link_por_capitulo():
    assert "github.com/OWASP/ASVS" in cite_url("ASVS-V2.1.1")
    assert "Authentication" in cite_url("ASVS-V2")
