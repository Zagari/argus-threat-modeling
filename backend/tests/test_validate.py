"""Validador de ancoragem (3.2) — a régua anti-alucinação, agnóstica de sistema."""

from __future__ import annotations

from app.argus.knowledge.store import LocalKG
from app.argus.knowledge.validate import validate_threats
from app.schemas import Mitigation, Threat


def _threat(tid: str, cwe_ids: list[str], capec_ids: list[str] | None = None, refs: list[str] | None = None) -> Threat:
    return Threat(
        id=tid, component_id="C1", element_type="Process", stride_category="Spoofing",
        title="t", attack_scenario="s", cwe_ids=cwe_ids, capec_ids=capec_ids or [],
        mitigations=[Mitigation(description="m", refs=refs or [])],
    )


def test_marca_grounded_e_remove_alucinacao():
    store = LocalKG()
    threats = [
        _threat("T1", ["CWE-287"]),                 # válido
        _threat("T2", ["CWE-99999"]),               # alucinação
        _threat("T3", ["CWE-287", "CWE-99999"]),    # misto
        _threat("T4", []),                          # sem âncora
    ]
    rep = validate_threats(threats, store, drop_invalid=True)
    assert threats[0].grounded is True
    assert threats[1].grounded is False and threats[1].cwe_ids == []          # falso removido
    assert threats[2].grounded is True and threats[2].cwe_ids == ["CWE-287"]  # mantém só o real
    assert threats[3].grounded is False
    assert rep.ids_valid == 2 and rep.ids_invalid == 2
    assert rep.groundedness == 0.5


def test_modo_medicao_nao_remove_e_penaliza_alucinacao():
    # Como na Fase 5 sobre o Cíclope: mede sem limpar; citar 1 ID falso = NÃO grounded.
    store = LocalKG()
    t = _threat("T1", ["CWE-287", "CWE-99999"])
    rep = validate_threats([t], store, drop_invalid=False)
    assert t.grounded is False
    assert t.cwe_ids == ["CWE-287", "CWE-99999"]   # nada removido
    assert rep.ids_valid == 1 and rep.ids_invalid == 1


def test_valida_ids_em_refs_de_texto_livre():
    store = LocalKG()
    t = _threat("T1", [], refs=["CWE-89", "CAPEC-66", "ASVS V2.1.1"])
    rep = validate_threats([t], store, drop_invalid=False)
    assert rep.ids_valid == 2 and t.grounded is True   # CWE-89 e CAPEC-66 reais (ASVS-subitem ignorado)
