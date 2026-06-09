"""Cadeia estendida (3.6b) — ATT&CK + D3FEND + NIST: catálogos + subgrafo + deep-links."""

from __future__ import annotations

from app.argus.knowledge.store import LocalKG
from app.report.render import cite_url


def test_catalogos_estendidos_carregados():
    kg = LocalKG()
    assert kg.exists("ATTACK", "T1078") is True
    assert kg.exists("Control", "NIST-AC-6") is True
    counts: dict[str, int] = {}
    for e in kg.iter_entities():
        counts[e.kind] = counts.get(e.kind, 0) + 1
    assert counts.get("ATTACK", 0) >= 500
    assert counts.get("D3FEND", 0) >= 100


def test_subgraph_cadeia_completa():
    sg = LocalKG().subgraph("api_gateway", "Spoofing")
    kinds = {n.kind for n in sg.nodes}
    assert {"CWE", "CAPEC", "ATTACK", "D3FEND", "Control"} <= kinds   # cadeia CWE→CAPEC→ATT&CK→D3FEND
    assert any(n.id.startswith("NIST-") for n in sg.nodes)            # + controle NIST
    node_ids = {n.id for n in sg.nodes}
    for e in sg.edges:
        assert e.source in node_ids and e.target in node_ids


def test_cite_url_nist_e_d3fend():
    assert "csf.tools" in cite_url("NIST-AC-6")
    assert "d3fend.mitre.org/technique/d3f:CredentialHardening" in cite_url("D3F-CredentialHardening")
