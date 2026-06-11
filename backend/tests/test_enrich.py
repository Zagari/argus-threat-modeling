"""E5 enriquecimento (3.2) — ancoragem + groundedness (modo mock = fallback determinístico)."""

from __future__ import annotations

from app.argus.knowledge import enrich as kg_enrich
from app.argus.knowledge.store import LocalKG
from app.schemas import Component, Threat


def _comp(cid: str, canonical: str) -> Component:
    return Component(id=cid, canonical=canonical, element_type="Process")


def _threat(tid: str, comp_id: str, stride: str) -> Threat:
    return Threat(id=tid, component_id=comp_id, element_type="Process",
                  stride_category=stride, title="t", attack_scenario="s")


def test_enrich_mock_ancora_cwe_reais_e_marca_grounded():
    store = LocalKG()
    comps = [_comp("C1", "api_gateway"), _comp("C2", "database_sql")]
    threats = [_threat("T1", "C1", "Spoofing"), _threat("T2", "C2", "Tampering")]

    rep = kg_enrich.enrich(threats, comps, store)

    for t in threats:
        assert t.cwe_ids, f"{t.id} sem CWE ancorada"
        assert t.grounded is True
        assert all(store.exists("CWE", c) for c in t.cwe_ids)   # todas reais
    assert rep.groundedness == 1.0
    assert rep.ids_invalid == 0


def test_enrich_anexa_contramedidas_com_refs_de_controle():
    store = LocalKG()
    comps = [_comp("C1", "api_gateway")]
    threats = [_threat("T1", "C1", "Spoofing")]
    kg_enrich.enrich(threats, comps, store)
    refs = [r for m in threats[0].mitigations for r in m.refs]
    assert any(r.startswith("ASVS-V") for r in refs)                       # controle citado
    assert all(store.exists("Control", r) for r in refs if r.startswith("ASVS-"))  # e real


def test_ref_filtra_ancora_alucinada_mantem_controle():
    """Anti-vazamento (Lote 1/A): refs mantêm controles e âncoras candidatas; descartam CWE/CAPEC fora."""
    allowed = {"CWE-89", "CAPEC-66", "T1190"}
    assert kg_enrich._ref_ok("ASVS-V2", allowed)        # controle → mantém
    assert kg_enrich._ref_ok("NIST-IA-2", allowed)      # controle → mantém
    assert kg_enrich._ref_ok("CWE-89", allowed)         # âncora candidata → mantém
    assert not kg_enrich._ref_ok("CWE-9999", allowed)   # âncora alucinada → descarta
    assert not kg_enrich._ref_ok("CAPEC-99999", allowed)
