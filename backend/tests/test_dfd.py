"""Testes do estágio E3 (DFD) — puros, sem ML/LLM.

Verificam a contenção em fronteiras de confiança e a marcação de `crosses_boundary`
(um fluxo cruza a fronteira quando origem e destino estão em zonas diferentes).
"""

from __future__ import annotations

from app.argus import dfd
from app.schemas import Component, Edge

# Fronteira cobrindo x∈[0.4,0.8], y∈[0.4,0.8]
_B = Component(id="B1", canonical="trust_boundary", element_type="TrustBoundary",
               bbox=[0.4, 0.4, 0.4, 0.4])
_IN1 = Component(id="C1", canonical="compute", element_type="Process", bbox=[0.50, 0.50, 0.05, 0.05])
_IN2 = Component(id="C3", canonical="database_sql", element_type="DataStore", bbox=[0.60, 0.60, 0.05, 0.05])
_OUT = Component(id="C2", canonical="actor_user", element_type="ExternalEntity", bbox=[0.10, 0.10, 0.05, 0.05])

_COMPONENTS = [_B, _IN1, _IN2, _OUT]


def test_containment() -> None:
    c = dfd.containment(_COMPONENTS)
    assert c["C1"] == {"B1"}
    assert c["C3"] == {"B1"}
    assert c["C2"] == set()


def test_mark_crossings() -> None:
    edges = [
        Edge(source="C2", target="C1"),  # fora -> dentro: CRUZA
        Edge(source="C1", target="C3"),  # dentro -> dentro: não cruza
    ]
    out = dfd.mark_crossings(_COMPONENTS, edges)
    assert out[0].crosses_boundary is True
    assert out[1].crosses_boundary is False


def test_summarize() -> None:
    edges = dfd.mark_crossings(_COMPONENTS, [Edge(source="C2", target="C1")])
    s = dfd.summarize(_COMPONENTS, edges)
    assert s["boundaries"] == 1
    assert s["crossing_flows"] == 1
    assert s["by_element_type"]["Process"] == 1
