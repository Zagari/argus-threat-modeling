"""Testes do estágio E2 (OCR + fusão + topologia) — rodam SEM torch/OCR.

Cobrem o que é puro/determinístico: o mapa de rótulos, a fusão ícone+rótulo (que ataca a
lacuna sintético-real) e a topologia em modo mock; além da degradação graciosa dos
endpoints quando OCR/detector não estão disponíveis.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app.argus import crosscheck, fusion, topology
from app.argus.labelmap import match_label
from app.schemas import Component, TextRegion


def _png_bytes() -> bytes:
    import base64

    b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    return base64.b64decode(b64)


def test_match_label_maps_known_synonyms() -> None:
    assert match_label("Application Load Balancer") == "load_balancer"
    assert match_label("AWS KMS") == "secrets"
    assert match_label("Amazon Simple Email Service") == "email_notify"
    assert match_label("Postgres") == "database_sql"
    assert match_label("Resource group") == "trust_boundary"
    assert match_label("xyzzy nonsense") is None


def test_fusion_corrects_class_from_label() -> None:
    # ícone mal classificado como actor_user, mas rotulado "Application Load Balancer"
    comp = Component(
        id="C1", canonical="actor_user", element_type="ExternalEntity",
        bbox=[0.10, 0.10, 0.10, 0.10], confidence=0.86,
    )
    region = TextRegion(text="Application Load Balancer", bbox=[0.10, 0.21, 0.12, 0.03])
    out = fusion.fuse([comp], [region])[0]
    assert out.label == "Application Load Balancer"
    assert out.canonical == "load_balancer"
    assert out.element_type == "Process"


def test_fusion_leaves_component_without_label_untouched() -> None:
    comp = Component(id="C1", canonical="compute", element_type="Process",
                     bbox=[0.10, 0.10, 0.10, 0.10], confidence=0.99)
    far_text = TextRegion(text="API Gateway", bbox=[0.80, 0.80, 0.10, 0.03])
    out = fusion.fuse([comp], [far_text])[0]
    assert out.canonical == "compute"
    assert out.label is None


def test_topology_mock_chains_components() -> None:
    comps = [
        Component(id="C1", canonical="actor_user", element_type="ExternalEntity"),
        Component(id="C2", canonical="api_gateway", element_type="Process"),
        Component(id="C3", canonical="database_sql", element_type="DataStore"),
    ]
    edges, name = topology.extract(b"fake", comps)  # ARGUS_LLM_MOCK=1 no conftest
    assert [(e.source, e.target) for e in edges] == [("C1", "C2"), ("C2", "C3")]
    assert name == ""  # mock não nomeia


def test_crosscheck_noop_in_mock() -> None:
    comps = [Component(id="C1", canonical="actor_user", element_type="ExternalEntity", confidence=0.4)]
    out = crosscheck.verify(b"fake", comps)  # ARGUS_LLM_MOCK=1 → no-op
    assert out[0].canonical == "actor_user"


def test_ocr_status_unavailable(client: TestClient) -> None:
    r = client.get("/stage/ocr/status")
    assert r.status_code == 200
    assert r.json()["available"] is False


def test_ocr_endpoint_503_without_engine(client: TestClient) -> None:
    files = {"file": ("d.png", io.BytesIO(_png_bytes()), "image/png")}
    assert client.post("/stage/ocr", files=files).status_code == 503


def test_topology_endpoint_503_without_detector(client: TestClient) -> None:
    files = {"file": ("d.png", io.BytesIO(_png_bytes()), "image/png")}
    assert client.post("/stage/topology", files=files).status_code == 503
