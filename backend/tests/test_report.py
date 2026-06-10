"""Relatório STRIDE — citações clicáveis, groundedness/DREAD (3.5) e estrutura Shostack (Fase 4)."""

from __future__ import annotations

from app.report.render import cite_url, to_html
from app.schemas import Component, Edge, Mitigation, Threat, ThreatModel


def test_cite_url_mapeia_fontes_oficiais():
    assert cite_url("CWE-89").endswith("/89.html")
    assert "capec.mitre.org" in cite_url("CAPEC-66")
    assert "nvd.nist.gov" in cite_url("CVE-2021-44228")
    assert cite_url("T1078").endswith("/techniques/T1078/")
    assert cite_url("T1078.001").endswith("/techniques/T1078/001/")
    assert cite_url("ASVS-V2")
    assert cite_url("nao-é-id") is None


def test_html_tem_ancoras_clicaveis_e_groundedness():
    tm = ThreatModel(
        system_name="D",
        meta={"groundedness": 0.9, "threats_grounded": 9, "threats_total": 10, "n_cves": 3, "dread_dist": {"Alto": 5}},
        components=[Component(id="C1", canonical="cache", element_type="DataStore", cve_ids=["CVE-2022-0543"])],
        threats=[Threat(id="T1", component_id="C1", element_type="DataStore", stride_category="Tampering",
                        title="t", attack_scenario="s", cwe_ids=["CWE-89"], grounded=True,
                        dread_score=6.8, dread_band="Alto")],
    )
    html = to_html(tm)
    assert '<a href="https://cwe.mitre.org' in html
    assert '<a href="https://nvd.nist.gov' in html
    assert "Groundedness:" in html and "90%" in html
    assert "DREAD 6.8" in html


def test_relatorio_profissional_estrutura_shostack():
    tm = ThreatModel(
        system_name="Loja Online",
        diagram_image="data:image/png;base64,QUJD",
        meta={"system": "argus", "provider": "gemini", "model": "x", "latency_s": 12.0,
              "groundedness": 1.0, "threats_grounded": 1, "threats_total": 1, "n_cves": 2,
              "dread_dist": {"Alto": 1}, "boundaries": 1, "crossing_flows": 1},
        components=[Component(id="C1", canonical="database_sql", element_type="DataStore",
                              label="RDS", cve_ids=["CVE-2022-0543"])],
        edges=[Edge(source="C0", target="C1", crosses_boundary=True)],
        threats=[Threat(id="T1", component_id="C1", element_type="DataStore", stride_category="Tampering",
                        title="SQL Injection no banco", attack_scenario="injeta SQL", impact="High",
                        cwe_ids=["CWE-89"], grounded=True, dread_score=8.0, dread_band="Alto",
                        dread={"damage": 8, "reproducibility": 7, "exploitability": 9, "affected": 6, "discoverability": 8},
                        mitigations=[Mitigation(description="Prepared statements", type="Preventive", refs=["ASVS-V5", "CWE-89"])])],
    )
    html = to_html(tm)
    for bloco in ("1. Escopo", "2. Ameaças identificadas", "3. Contramedidas", "4. Cobertura"):
        assert bloco in html, bloco
    assert "Riscos prioritários" in html                       # top-riscos ranqueado
    assert "Cobertura STRIDE-per-element" in html              # checklist Shostack Q4
    assert "data:image/png;base64,QUJD" in html                # diagrama anotado embutido
    assert "Damage 8" in html and "Discoverability 8" in html  # DREAD por dimensão
    assert "ASVS-V5" in html                                   # contramedida consolidada (controle)
