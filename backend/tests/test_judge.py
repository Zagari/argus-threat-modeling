"""LLM-as-judge (Fase 5, Lote 5.2): cegueira (anonimização) + agregação ponderada — offline, sem LLM."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))
import judge  # noqa: E402


def _tm():
    return {
        "system_name": "Loja Online (AWS)",
        "components": [{"id": "C1", "canonical": "database_sql", "element_type": "DataStore", "label": "RDS"}],
        "meta": {"system": "argus", "provider": "gemini"},
        "threats": [
            {
                "id": "THR-1", "component_id": "C1", "element_type": "DataStore", "stride_category": "Tampering",
                "title": "SQLi detectada pelo ARGUS", "attack_scenario": "injeção no RDS",
                "provenance": "argus", "cwe_ids": ["CWE-89"],
            }
        ],
    }


def test_anonymize_remove_provenance_e_rotulos():
    threats = judge.anonymize_report(_tm())
    assert "provenance" not in threats[0]              # provenance removido
    blob = str(threats).lower()
    assert "argus" not in blob and "ciclope" not in blob and "cíclope" not in blob


def test_render_pointwise_eh_cego():
    prompt = judge.render_pointwise(_tm()).lower()
    # o juiz NÃO pode ver qual ferramenta gerou (cegueira)
    assert "argus" not in prompt
    assert "ciclope" not in prompt and "cíclope" not in prompt
    # mas a rubrica e o contexto têm de estar lá
    assert "cobertura stride" in prompt
    assert "todas as categorias stride aplicáveis" in prompt  # âncora 5 de coverage
    assert "database_sql" in prompt                            # contexto de arquitetura


def test_weighted_total_extremos_e_misto():
    def scores(**kw):
        return [judge.DimensionScore(dimension=d, rationale="x", score=kw[d]) for d in judge.DIMENSIONS]

    todos5 = judge.weighted_total(scores(coverage=5, specificity=5, actionability=5, severity_calibration=5, consistency=5))
    assert todos5["weighted_1to5"] == 5.0 and todos5["score_0to100"] == 100.0
    todos1 = judge.weighted_total(scores(coverage=1, specificity=1, actionability=1, severity_calibration=1, consistency=1))
    assert todos1["weighted_1to5"] == 1.0 and todos1["score_0to100"] == 0.0
    misto = judge.weighted_total(scores(coverage=5, specificity=3, actionability=4, severity_calibration=2, consistency=1))
    assert misto["weighted_1to5"] == 3.25  # 5*.25+3*.25+4*.20+2*.15+1*.15
    assert abs(misto["score_0to100"] - 56.25) < 0.1


def test_weights_somam_um():
    assert abs(sum(judge.WEIGHTS.values()) - 1.0) < 1e-9
    assert set(judge.WEIGHTS) == set(judge.DIMENSIONS)
