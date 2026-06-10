"""Curadoria por classe de componente (3.9): todo id citado é REAL e a classe refina o subgrafo."""

from __future__ import annotations

import pytest

from app.argus.knowledge import seeds
from app.argus.knowledge.store import LocalKG, panorama

KG = LocalKG()


def _cells(mapping: dict[str, dict[str, list[str]]]) -> list[tuple[str, str, str]]:
    return [(cls, stride, i) for cls, by in mapping.items() for stride, ids in by.items() for i in ids]


@pytest.mark.parametrize("cls,stride,cwe", _cells(seeds.CLASS_STRIDE_TO_CWE))
def test_curadoria_cwe_existe(cls: str, stride: str, cwe: str) -> None:
    assert KG.exists("CWE", cwe), f"CWE inexistente na curadoria de {cls}/{stride}: {cwe}"


@pytest.mark.parametrize(
    "cls,stride,ctrl",
    _cells(seeds.CLASS_STRIDE_TO_ASVS) + _cells(seeds.CLASS_STRIDE_TO_NIST),
)
def test_curadoria_controle_existe(cls: str, stride: str, ctrl: str) -> None:
    assert KG.exists("Control", ctrl), f"controle inexistente na curadoria de {cls}/{stride}: {ctrl}"


def test_classe_refina_o_subgrafo() -> None:
    # database_sql/Tampering traz SQLi (CWE-89); curadoria específica do ativo.
    assert "CWE-89" in KG.subgraph("database_sql", "Tampering").ids("CWE")
    # object_storage/InfoDisc traz permissões incorretas (CWE-732) — AUSENTE na base por propriedade.
    assert "CWE-732" in KG.subgraph("object_storage", "Information Disclosure").ids("CWE")
    assert "CWE-732" not in seeds.STRIDE_TO_CWE["Information Disclosure"]


def test_compat_preservada() -> None:
    # contratos dos testes existentes seguem válidos
    assert "CWE-287" in KG.subgraph("api_gateway", "Spoofing").ids("CWE")
    assert "CWE-20" in KG.subgraph("trust_boundary", "Tampering").ids("CWE")  # fallback à base


def test_panorama_une_as_6_stride() -> None:
    pan = panorama(KG, "database_sql")
    assert len([n for n in pan.nodes if n.kind == "Stride"]) == 6
    pan_nodes = {(n.kind, n.id) for n in pan.nodes}
    one = KG.subgraph("database_sql", "Information Disclosure")
    assert all((n.kind, n.id) in pan_nodes for n in one.nodes)
