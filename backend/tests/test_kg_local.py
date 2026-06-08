"""KG local (3.1): subgrafo por (classe, STRIDE) + validação de IDs (anti-alucinação)."""

from __future__ import annotations

from app.argus.knowledge.store import LocalKG


def test_exists_valida_ids_reais_e_pega_inexistentes():
    kg = LocalKG()
    assert kg.exists("CWE", "CWE-287") is True       # da semente
    assert kg.exists("CWE", "CWE-1004") is True       # só no catálogo completo (não é semente)
    assert kg.exists("CWE", "CWE-99999") is False     # inexistente → pega alucinação
    assert kg.exists("CAPEC", "CAPEC-66") is True      # SQL Injection
    assert kg.exists("Control", "ASVS-V2") is True


def test_catalogo_completo_carregado():
    counts: dict[str, int] = {}
    for e in LocalKG().iter_entities():
        counts[e.kind] = counts.get(e.kind, 0) + 1
    assert counts.get("CWE", 0) >= 800
    assert counts.get("CAPEC", 0) >= 500
    assert counts.get("Control", 0) >= 14


def test_subgraph_spoofing_tem_cwe_capec_e_controle():
    sg = LocalKG().subgraph("api_gateway", "Spoofing")
    assert not sg.is_empty()
    assert "CWE-287" in sg.ids("CWE")                  # Improper Authentication
    assert sg.ids("CAPEC")                              # CWE↔CAPEC veio do catálogo CAPEC
    assert "ASVS-V2" in sg.ids("Control")              # Authentication
    # toda aresta referencia nós presentes no subgrafo
    node_ids = {n.id for n in sg.nodes}
    for e in sg.edges:
        assert e.source in node_ids and e.target in node_ids


def test_subgraph_citavel_tem_nomes_e_urls():
    sg = LocalKG().subgraph("database_sql", "Tampering")
    cwe = next(n for n in sg.nodes if n.kind == "CWE")
    assert cwe.name and cwe.url and cwe.url.startswith("https://")
