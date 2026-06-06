"""Testes do estágio E1 (detector) — rodam SEM torch/ultralytics.

Sem pesos configurados (caso do CI e do backend de produção), o detector deve
se reportar indisponível e o endpoint deve responder 503 com mensagem clara —
nunca quebrar a importação do app.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient


def _png_bytes() -> bytes:
    # PNG 1x1 mínimo válido (não precisa de Pillow para montar)
    import base64

    b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    return base64.b64decode(b64)


def test_detect_status_unavailable_without_weights(client: TestClient) -> None:
    r = client.get("/stage/detect/status")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert "reason" in body


def test_detect_returns_503_without_weights(client: TestClient) -> None:
    files = {"file": ("d.png", io.BytesIO(_png_bytes()), "image/png")}
    r = client.post("/stage/detect", files=files)
    assert r.status_code == 503
    assert "detector" in r.json()["detail"].lower() or "ARGUS_DETECTOR" in r.json()["detail"]


def test_detect_empty_file_is_400(client: TestClient) -> None:
    files = {"file": ("d.png", io.BytesIO(b""), "image/png")}
    r = client.post("/stage/detect", files=files)
    assert r.status_code == 400
