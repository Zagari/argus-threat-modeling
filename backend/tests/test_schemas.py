"""Contrato do ThreatModel — base compartilhada por Cíclope e ARGUS."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import ThreatModel


def test_threatmodel_valido():
    tm = ThreatModel.model_validate(
        {
            "system_name": "Teste",
            "components": [
                {"id": "C1", "canonical": "api_gateway", "element_type": "Process", "label": "APIM"}
            ],
            "edges": [{"source": "C1", "target": "C1"}],
            "threats": [
                {
                    "id": "THR-001",
                    "component_id": "C1",
                    "element_type": "Process",
                    "stride_category": "Spoofing",
                    "title": "x",
                    "attack_scenario": "y",
                }
            ],
        }
    )
    assert tm.threats[0].risk_score == 1  # default
    assert tm.threats[0].provenance == "argus"  # default
    assert tm.components[0].canonical == "api_gateway"


def test_categoria_stride_invalida_rejeitada():
    with pytest.raises(ValidationError):
        ThreatModel.model_validate(
            {
                "threats": [
                    {
                        "id": "T",
                        "component_id": "C1",
                        "element_type": "Process",
                        "stride_category": "Sabotagem",  # inválida
                        "title": "x",
                        "attack_scenario": "y",
                    }
                ]
            }
        )


def test_risk_score_fora_de_faixa_rejeitado():
    with pytest.raises(ValidationError):
        ThreatModel.model_validate(
            {
                "threats": [
                    {
                        "id": "T",
                        "component_id": "C1",
                        "element_type": "Process",
                        "stride_category": "Tampering",
                        "title": "x",
                        "attack_scenario": "y",
                        "risk_score": 99,  # > 25
                    }
                ]
            }
        )
