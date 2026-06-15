"""Testes do estágio E4 (STRIDE-per-element) — rodam em modo mock (sem LLM/ML).

Verificam o diferencial do ARGUS: as ameaças respeitam a matriz STRIDE-per-element
(o filtro determinístico), fronteiras não geram ameaça e a pontuação fica em 1..25.
"""

from __future__ import annotations

import base64
import io

from fastapi.testclient import TestClient

from app.argus import stride
from app.schemas import Component, Edge
from app.taxonomy import applicable_categories


def _png() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def test_stride_mock_respects_matrix() -> None:
    comps = [
        Component(id="C1", canonical="api_gateway", element_type="Process"),
        Component(id="C2", canonical="database_sql", element_type="DataStore"),
        Component(id="C3", canonical="vpc", element_type="TrustBoundary"),
    ]
    threats = stride.generate(comps, [Edge(source="C1", target="C2", crosses_boundary=True)])

    assert threats, "deveria gerar ao menos uma ameaça"
    assert all(t.component_id != "C3" for t in threats), "fronteira não gera ameaça"
    by_id = {c.id: c for c in comps}
    for t in threats:
        allowed = applicable_categories(by_id[t.component_id].element_type)
        assert t.stride_category in allowed, "categoria fora da matriz do elemento"
        assert 1 <= t.risk_score <= 25
        assert t.provenance == "argus" and t.grounded is False


def test_to_threats_filtra_matriz_e_only_cells() -> None:
    """A matriz como GERADOR: `_to_threats` filtra fora-da-matriz/inexistentes, numera sequencial,
    e `only_cells` (usado pelo backstop) mantém só as células pedidas."""
    comps = [
        Component(id="C1", canonical="api_gateway", element_type="Process"),
        Component(id="C2", canonical="database_sql", element_type="DataStore"),
    ]
    by_id = {c.id: c for c in comps}

    def g(cid: str, cat: str) -> stride._ThreatGen:
        return stride._ThreatGen(component_id=cid, stride_category=cat, title="t", attack_scenario="s")

    gens = [g("C1", "Spoofing"), g("C2", "Spoofing"), g("C2", "Tampering"), g("C9", "Spoofing")]

    out = stride._to_threats(gens, by_id, 0)  # descarta Spoofing no DataStore (fora da matriz) e C9 (inexistente)
    assert {(t.component_id, str(t.stride_category)) for t in out} == {("C1", "Spoofing"), ("C2", "Tampering")}
    assert [t.id for t in out] == ["THR-001", "THR-002"]

    out2 = stride._to_threats(gens, by_id, 5, only_cells={("C2", "Tampering")})  # backstop só preenche a lacuna
    assert [(t.component_id, str(t.stride_category)) for t in out2] == [("C2", "Tampering")]
    assert out2[0].id == "THR-006"  # numera a partir de start+1


def test_piso_da_matriz_required_cells() -> None:
    """O piso requer 1 célula por (componente × categoria aplicável) — não o subconjunto que o LLM amostrou."""
    comps = [
        Component(id="C1", canonical="api_gateway", element_type="Process"),
        Component(id="C2", canonical="database_sql", element_type="DataStore"),
    ]
    required = {(c.id, cat) for c in comps for cat in applicable_categories(c.element_type)}
    assert len(required) == len(applicable_categories("Process")) + len(applicable_categories("DataStore"))
    assert ("C1", "Spoofing") in required
    assert ("C2", "Spoofing") not in required  # Spoofing não é aplicável a DataStore


def test_analyze_argus_503_without_detector(client: TestClient) -> None:
    files = {"file": ("d.png", io.BytesIO(_png()), "image/png")}
    r = client.post("/analyze?system=argus", files=files)
    assert r.status_code == 503
