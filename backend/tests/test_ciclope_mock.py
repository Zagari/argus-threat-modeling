"""Cíclope ponta a ponta em modo mock (sem rede) + geração de PDF."""

from __future__ import annotations

from pathlib import Path

FIGURA = Path(__file__).resolve().parents[2] / "data" / "gold" / "figura-1-arquitetura-1.jpg"


def test_analyze_ciclope_retorna_threatmodel(client):
    assert FIGURA.exists(), f"diagrama-exemplo não encontrado: {FIGURA}"
    with FIGURA.open("rb") as f:
        r = client.post(
            "/analyze",
            params={"system": "ciclope"},
            files={"file": ("fig1.jpg", f.read(), "image/jpeg")},
        )
    assert r.status_code == 200, r.text
    tm = r.json()
    assert len(tm["threats"]) >= 1
    assert all(t["provenance"] == "ciclope" for t in tm["threats"])
    assert tm["components"]


def test_argus_requer_detector(client):
    # ARGUS (E1→E4) precisa do detector; sem pesos/ML, responde 503 gracioso.
    with FIGURA.open("rb") as f:
        r = client.post(
            "/analyze",
            params={"system": "argus"},
            files={"file": ("fig1.jpg", f.read(), "image/jpeg")},
        )
    assert r.status_code == 503


def test_report_pdf_gerado(client):
    with FIGURA.open("rb") as f:
        tm = client.post(
            "/analyze", params={"system": "ciclope"}, files={"file": ("f.jpg", f.read(), "image/jpeg")}
        ).json()
    r = client.post("/report/pdf", json=tm)
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"
