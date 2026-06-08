"""CVEs reais por componente (3.3) — lê o cache NVD versionado, sem rede no CI."""

from __future__ import annotations

from app.argus.knowledge import cve as kg_cve
from app.schemas import Component


def _comp(canonical: str) -> Component:
    return Component(id="C1", canonical=canonical, element_type="Process")


def test_cves_reais_para_classe_com_cpe():
    cves = kg_cve.cves_for_component(_comp("cache"))  # redis / memcached
    assert cves, "esperava CVEs reais para a classe 'cache'"
    for c in cves:
        assert c["id"].startswith("CVE-")
        assert c["cvss"] is not None
        assert c["url"].startswith("https://nvd.nist.gov/")


def test_classe_sem_cpe_nao_retorna_cve():
    assert kg_cve.cves_for_component(_comp("actor_user")) == []


def test_is_known_distingue_real_de_inexistente():
    cache = kg_cve.cves_for_component(_comp("secrets"))  # hashicorp vault
    assert cache and kg_cve.is_known(cache[0]["id"]) is True
    assert kg_cve.is_known("CVE-9999-99999") is False
    assert kg_cve.total_known() >= 50
