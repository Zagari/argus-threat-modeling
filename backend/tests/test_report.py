"""PDF/HTML enriquecido (3.5) — citações clicáveis + groundedness/DREAD no relatório."""

from __future__ import annotations

from app.report.render import cite_url, to_html
from app.schemas import Component, Threat, ThreatModel


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
