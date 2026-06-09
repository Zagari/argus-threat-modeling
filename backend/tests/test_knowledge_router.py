"""Endpoints /knowledge/* (3.5) — subgrafo, entidade, busca, opções."""

from __future__ import annotations


def test_options(client):
    r = client.get("/knowledge/options")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["classes"] and "Spoofing" in body["stride"]


def test_subgraph(client):
    r = client.get("/knowledge/subgraph", params={"canonical": "api_gateway", "stride": "Spoofing"})
    assert r.status_code == 200, r.text
    sg = r.json()
    assert sg["nodes"] and any(n["id"] == "CWE-287" for n in sg["nodes"])
    assert any(n["kind"] == "CAPEC" for n in sg["nodes"])


def test_entity_ok_e_404(client):
    r = client.get("/knowledge/entity/CWE/CWE-287")
    assert r.status_code == 200 and r.json()["id"] == "CWE-287"
    assert client.get("/knowledge/entity/CWE/CWE-99999").status_code == 404


def test_search(client):
    r = client.get("/knowledge/search", params={"q": "authentication"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] in ("semântica", "substring")
    assert body["hits"] and any("authentication" in i["name"].lower() for i in body["hits"])
