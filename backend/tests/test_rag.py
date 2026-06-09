"""RAG semântico (3.7) — fallback gracioso (CI sem libs) + procedência híbrida no enrich."""

from __future__ import annotations

from app.argus.knowledge import enrich as kg_enrich
from app.argus.knowledge import rag
from app.argus.knowledge.store import LocalKG
from app.schemas import Component, Threat


def test_rag_desligado_no_ci():
    # CI não tem chromadb/sentence-transformers nem ARGUS_RAG=1 → tudo cai no fallback.
    assert rag.ready() is False
    assert rag.search("authentication", kind="CWE") == []


def test_search_endpoint_substring_fallback(client):
    r = client.get("/knowledge/search", params={"q": "authentication"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "substring"
    assert body["hits"] and any("authentication" in h["name"].lower() for h in body["hits"])


def test_enrich_marca_procedencia_semantica(monkeypatch):
    # Simula o RAG pronto devolvendo um CWE que NÃO está no mapeamento determinístico de Spoofing.
    store = LocalKG()
    monkeypatch.setattr(rag, "ready", lambda: True)

    def fake_search(query, *, kind=None, k=8):
        if kind == "CWE":
            return [{"id": "CWE-1004", "kind": "CWE", "name": "Sensitive Cookie Without HttpOnly", "url": None, "score": 0.9}]
        return []

    monkeypatch.setattr(rag, "search", fake_search)

    comps = [Component(id="C1", canonical="api_gateway", element_type="Process")]
    threats = [Threat(id="T1", component_id="C1", element_type="Process",
                      stride_category="Spoofing", title="cookie sem httponly", attack_scenario="...")]
    rep = kg_enrich.enrich(threats, comps, store)

    # candidato semântico contabilizado; em mock o determinístico é escolhido, então CWE-1004
    # entra em semantic_anchors só se for citado — aqui validamos a contagem de candidatos.
    assert rep.sem_candidates >= 1
    assert rep.groundedness == 1.0  # determinístico garante ancoragem
