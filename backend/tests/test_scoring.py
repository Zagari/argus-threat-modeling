"""DREAD determinístico (3.4) — defaults por (elemento × categoria); reprodutível."""

from __future__ import annotations

from app.argus import scoring
from app.schemas import Threat


def _threat(tid: str, element_type: str, stride: str) -> Threat:
    return Threat(id=tid, component_id="C1", element_type=element_type, stride_category=stride,
                  title="t", attack_scenario="s")


def test_dread_deterministico_e_estavel():
    a = scoring.dread("Process", "Spoofing")
    b = scoring.dread("Process", "Spoofing")
    assert a == b                                  # mesma entrada → mesma nota
    assert set(a) >= {"damage", "reproducibility", "exploitability", "affected", "discoverability", "score", "band"}
    assert all(1 <= a[k] <= 10 for k in ("damage", "reproducibility", "exploitability", "affected", "discoverability"))
    assert 1 <= a["score"] <= 10


def test_modificador_por_elemento():
    # DataStore soma +Damage e +Affected sobre a base da categoria.
    base = scoring.dread("Process", "Information Disclosure")
    ds = scoring.dread("DataStore", "Information Disclosure")
    assert ds["damage"] == min(10, base["damage"] + 1)
    assert ds["affected"] == min(10, base["affected"] + 1)


def test_faixas():
    assert scoring._band(8.0) == "Crítico"
    assert scoring._band(6.5) == "Alto"
    assert scoring._band(4.0) == "Médio"
    assert scoring._band(3.9) == "Baixo"


def test_apply_e_distribuicao():
    threats = [
        _threat("T1", "Process", "Elevation of Privilege"),
        _threat("T2", "DataStore", "Denial of Service"),
        _threat("T3", "ExternalEntity", "Spoofing"),
    ]
    scoring.apply(threats)
    for t in threats:
        assert t.dread and t.dread_score is not None and t.dread_band
    dist = scoring.distribution(threats)
    assert sum(dist.values()) == 3
