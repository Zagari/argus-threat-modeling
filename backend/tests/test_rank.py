"""Ranquear antes de cortar (3.10): vizinhos ordenados por relevância do catálogo, não first-N."""

from __future__ import annotations

from app.argus.knowledge import seeds
from app.argus.knowledge.store import LocalKG

KG = LocalKG()


def _rank(kind: str, eid: str) -> int:
    e = KG.entity(kind, eid)
    return e.rank if e else 0


def test_capec_ordenado_por_rank() -> None:
    # acha um CWE-semente com mais de 3 CAPECs (onde o corte importa)
    cwe = next(c for c in seeds.STRIDE_TO_CWE["Tampering"] if len(KG.capec_by_cwe(c)) > 3)
    capecs = KG.capec_by_cwe(cwe)
    ranks = [_rank("CAPEC", c) for c in capecs]
    assert ranks == sorted(ranks, reverse=True)  # não-crescente (top-rank primeiro)
    assert ranks[0] > 0  # há sinal de relevância de verdade
    # o corte [:3] do subgrafo pega os de maior rank, não os primeiros do catálogo
    assert min(_rank("CAPEC", c) for c in capecs[:3]) >= _rank("CAPEC", capecs[-1])


def test_asvs_reqs_ordenado_por_rank() -> None:
    reqs = KG.reqs_by_chapter("ASVS-V2")  # Authentication tem vários requisitos
    assert len(reqs) > 3
    ranks = [_rank("Control", r) for r in reqs]
    assert ranks == sorted(ranks, reverse=True)
    assert ranks[0] >= ranks[-1]
