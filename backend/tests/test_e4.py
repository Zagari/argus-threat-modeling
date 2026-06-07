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


def test_analyze_argus_503_without_detector(client: TestClient) -> None:
    files = {"file": ("d.png", io.BytesIO(_png()), "image/png")}
    r = client.post("/analyze?system=argus", files=files)
    assert r.status_code == 503
