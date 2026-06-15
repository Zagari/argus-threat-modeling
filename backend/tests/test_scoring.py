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


_STRIDE = ["Spoofing", "Tampering", "Repudiation", "Information Disclosure", "Denial of Service", "Elevation of Privilege"]


def test_risk_score_coerente_com_dread():
    """O 5×5 deriva do DREAD → sem a contradição que o juiz flagou (dread Alto/Crítico × risk baixo)."""
    threats = [_threat(f"T{i}", et, cat) for i, et in enumerate(["Process", "DataStore", "DataFlow"]) for cat in _STRIDE]
    scoring.apply(threats)
    for t in threats:
        assert t.likelihood in ("High", "Medium", "Low")          # derivado, não o default cego
        assert t.impact in ("Critical", "High", "Medium", "Low")
        assert 1 <= t.risk_score <= 25
        if t.dread_band in ("Crítico", "Alto"):                    # nunca alto no DREAD e baixo no 5×5
            assert t.risk_score >= 5, f"{t.stride_category}/{t.element_type}: {t.dread_band} mas risk {t.risk_score}"
    # determinístico: mesma entrada → mesmo risk_score
    again = [_threat(f"U{i}", et, cat) for i, et in enumerate(["Process", "DataStore", "DataFlow"]) for cat in _STRIDE]
    scoring.apply(again)
    assert [t.risk_score for t in threats] == [t.risk_score for t in again]


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
