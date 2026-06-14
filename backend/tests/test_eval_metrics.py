"""Agregação do estudo comparativo (Fase 5): média ± desvio entre as N execuções (puro, sem ML/LLM)."""

from __future__ import annotations

import sys
from pathlib import Path

# eval/ fica fora do backend; o módulo de métricas é stdlib-only (testável na CI).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))
import metrics  # noqa: E402


def test_aggregate_ignora_none_e_calcula_desvio():
    assert metrics.aggregate([]) == {"mean": None, "std": None, "min": None, "max": None, "n": 0}
    um = metrics.aggregate([5])
    assert um["mean"] == 5 and um["std"] == 0.0 and um["n"] == 1
    # a variância que o usuário observou: ARGUS oscilando 19/21/22 ameaças (None é ignorado)
    a = metrics.aggregate([19, 21, 22, None])
    assert a["n"] == 3 and a["min"] == 19 and a["max"] == 22
    assert abs(a["mean"] - 20.6667) < 1e-3
    assert abs(a["std"] - 1.2472) < 1e-3  # pstdev([19,21,22])


def _run(image, system, run, **m):
    base = {"n_threats": None, "groundedness": None, "id_validity": None, "ids_valid": None,
            "ids_invalid": None, "n_cves": None, "latency_s": None, "cost_usd": None, "dread_dist": None}
    return {"image": image, "system": system, "run": run, "metrics": {**base, **m}}


def test_summarize_agrupa_por_imagem_sistema():
    measured = [
        _run("fig2.jpg", "argus", 0, n_threats=19, groundedness=1.0, dread_dist={"Crítico": 2, "Alto": 5}),
        _run("fig2.jpg", "argus", 1, n_threats=21, groundedness=1.0, dread_dist={"Crítico": 4, "Alto": 5}),
        _run("fig2.jpg", "argus", 2, n_threats=22, groundedness=1.0, dread_dist={"Crítico": 3, "Alto": 6}),
        _run("fig2.jpg", "ciclope", 0, n_threats=10, groundedness=0.6),
    ]
    s = metrics.summarize(measured)
    assert set(s) == {("fig2.jpg", "argus"), ("fig2.jpg", "ciclope")}
    argus = s[("fig2.jpg", "argus")]
    assert argus["n_runs"] == 3
    assert abs(argus["n_threats"]["mean"] - 20.6667) < 1e-3
    assert argus["groundedness"]["mean"] == 1.0 and argus["groundedness"]["std"] == 0.0
    assert argus["dread_dist"]["Crítico"]["mean"] == 3.0  # média de 2,4,3
    assert s[("fig2.jpg", "ciclope")]["n_runs"] == 1


def test_format_table_tem_cabecalho_e_media_desvio():
    measured = [_run("fig1.jpg", "ciclope", 0, n_threats=12, groundedness=0.5, latency_s=8.0)]
    table = metrics.format_table(metrics.summarize(measured))
    assert "| Imagem | Sistema |" in table
    assert "fig1.jpg" in table and "ciclope" in table
    assert "±" in table  # média±desvio
