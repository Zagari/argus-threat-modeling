"""Painel comparativo (Fase 4, frente 3): a MESMA régua mede os dois; diff por (classe × STRIDE)."""

from __future__ import annotations

from app.compare import diff
from app.schemas import Component, Threat, ThreatModel


def _tm(system: str, *, threats: list[Threat], meta: dict | None = None) -> ThreatModel:
    return ThreatModel(
        system_name=system,
        components=[
            Component(id="C1", canonical="database_sql", element_type="DataStore"),
            Component(id="C2", canonical="api_gateway", element_type="Process"),
        ],
        threats=threats,
        meta={"system": system, **(meta or {})},
    )


def test_groundedness_medida_nos_dois_e_diff():
    # Cíclope cita um CWE inexistente (alucinação) → groundedness baixa; SEM meta de validação.
    ciclope = _tm("ciclope", threats=[
        Threat(id="T1", component_id="C1", element_type="DataStore", stride_category="Tampering",
               title="SQLi", attack_scenario="s", cwe_ids=["CWE-89", "CWE-99999"]),
    ])
    # ARGUS: CWE real + já validado (E5) → groundedness alta; e uma ameaça a mais (só-ARGUS).
    argus = _tm("argus", meta={"groundedness": 1.0, "ids_valid": 2, "ids_invalid": 0}, threats=[
        Threat(id="A1", component_id="C1", element_type="DataStore", stride_category="Tampering",
               title="SQLi", attack_scenario="s", cwe_ids=["CWE-89"], grounded=True),
        Threat(id="A2", component_id="C2", element_type="Process", stride_category="Spoofing",
               title="Auth bypass", attack_scenario="s", cwe_ids=["CWE-287"], grounded=True),
    ])

    res = diff(ciclope, argus)

    # régua única: o Cíclope foi medido aqui (alucinou → não-grounded), o ARGUS manteve o do E5
    assert res["ciclope"]["groundedness"] == 0.0
    assert res["ciclope"]["ids_invalid"] == 1  # CWE-99999
    assert res["argus"]["groundedness"] == 1.0
    # diff por (classe × STRIDE): (database_sql, Tampering) é comum; (api_gateway, Spoofing) só-ARGUS
    assert res["diff"]["n_common"] == 1
    assert res["diff"]["n_only_argus"] == 1
    assert res["diff"]["n_only_ciclope"] == 0
    assert {"canonical": "api_gateway", "stride": "Spoofing"} in res["diff"]["only_argus"]
