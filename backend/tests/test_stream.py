"""Capabilities + streaming SSE por estágio (modo mock, sem rede)."""

from __future__ import annotations

import json
from pathlib import Path

FIGURA = Path(__file__).resolve().parents[2] / "data" / "gold" / "figura-1-arquitetura-1.jpg"


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    """Quebra o corpo SSE em (evento, data) por quadro separado por linha em branco."""
    out: list[tuple[str, dict]] = []
    for frame in text.split("\n\n"):
        frame = frame.strip()
        if not frame:
            continue
        event = "message"
        data_lines: list[str] = []
        for line in frame.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].lstrip())
        data = json.loads("\n".join(data_lines)) if data_lines else {}
        out.append((event, data))
    return out


def test_capabilities(client):
    r = client.get("/capabilities")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "argus_ml" in body and isinstance(body["argus_ml"], bool)
    assert "llm" in body and "provider" in body["llm"]
    # Em CI/mock não há detector configurado.
    assert body["argus_ml"] is False


def test_stream_ciclope_emite_start_e_done(client):
    with FIGURA.open("rb") as f:
        r = client.post(
            "/analyze/stream",
            params={"system": "ciclope"},
            files={"file": ("fig1.jpg", f.read(), "image/jpeg")},
        )
    assert r.status_code == 200, r.text
    events = _parse_sse(r.text)
    names = [e for e, _ in events]
    assert names[0] == "start"
    assert "done" in names
    done = next(d for e, d in events if e == "done")
    tm = done["threat_model"]
    assert tm["threats"] and all(t["provenance"] == "ciclope" for t in tm["threats"])


def test_stream_argus_sem_detector_emite_erro(client):
    # ARGUS exige o detector; sem pesos/ML o stream emite 'start' e depois 'error' (503).
    with FIGURA.open("rb") as f:
        r = client.post(
            "/analyze/stream",
            params={"system": "argus"},
            files={"file": ("fig1.jpg", f.read(), "image/jpeg")},
        )
    assert r.status_code == 200, r.text
    events = _parse_sse(r.text)
    names = [e for e, _ in events]
    assert names[0] == "start"
    assert "error" in names
    err = next(d for e, d in events if e == "error")
    assert err["status"] == 503
