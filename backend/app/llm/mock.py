"""ThreatModel canônico de mock — usado quando ARGUS_LLM_MOCK=1.

Permite rodar o app e os testes sem chave de API nem rede (CI offline, demos).
Não pretende ser realista; só exercita o contrato ponta a ponta.
"""

from __future__ import annotations

from app.schemas import Component, Edge, Mitigation, Threat, ThreatModel


def mock_threat_model(system_name: str = "Sistema (mock)", provenance: str = "ciclope") -> ThreatModel:
    components = [
        Component(id="C1", canonical="actor/user", label="Usuários", element_type="ExternalEntity"),
        Component(id="C2", canonical="api_gateway", label="API Gateway", element_type="Process"),
        Component(id="C3", canonical="database_sql", label="Banco de Dados", element_type="DataStore"),
    ]
    edges = [
        Edge(source="C1", target="C2", label="HTTPS", crosses_boundary=True),
        Edge(source="C2", target="C3", label="SQL"),
    ]
    threats = [
        Threat(
            id="THR-001",
            component_id="C2",
            element_type="Process",
            stride_category="Spoofing",
            title="Falsificação de identidade no API Gateway",
            attack_scenario="Atacante reutiliza tokens vazados para se passar por usuário legítimo.",
            likelihood="High",
            impact="High",
            risk_score=16,
            cwe_ids=["CWE-287"],
            mitigations=[
                Mitigation(description="Exigir MFA e validar tokens com expiração curta.", refs=["ASVS V2.1.1"])
            ],
            provenance=provenance,  # type: ignore[arg-type]
        ),
        Threat(
            id="THR-002",
            component_id="C3",
            element_type="DataStore",
            stride_category="Information Disclosure",
            title="Vazamento de dados sensíveis no banco",
            attack_scenario="SQL injection no gateway permite leitura não autorizada de registros.",
            likelihood="Medium",
            impact="Critical",
            risk_score=20,
            cwe_ids=["CWE-89"],
            mitigations=[
                Mitigation(description="Usar prepared statements e criptografia em repouso.", refs=["ASVS V5.3.4"])
            ],
            provenance=provenance,  # type: ignore[arg-type]
        ),
        Threat(
            id="THR-003",
            component_id="C2",
            element_type="Process",
            stride_category="Tampering",
            title="Manipulação de parâmetros na API",
            attack_scenario="Atacante altera payloads para burlar validações de negócio no gateway.",
            likelihood="Medium",
            impact="High",
            risk_score=12,
            cwe_ids=["CWE-20"],
            mitigations=[Mitigation(description="Validar e sanitizar toda entrada no servidor.", refs=["ASVS V5.1.3"])],
            provenance=provenance,  # type: ignore[arg-type]
        ),
        Threat(
            id="THR-004",
            component_id="C2",
            element_type="Process",
            stride_category="Denial of Service",
            title="Exaustão de recursos no gateway",
            attack_scenario="Flood de requisições sem rate limiting derruba o serviço.",
            likelihood="Medium",
            impact="Medium",
            risk_score=9,
            cwe_ids=["CWE-400"],
            mitigations=[Mitigation(description="Aplicar rate limiting e autoscaling.", type="Detective", refs=["ASVS V2.2.1"])],
            provenance=provenance,  # type: ignore[arg-type]
        ),
        Threat(
            id="THR-005",
            component_id="C3",
            element_type="DataStore",
            stride_category="Repudiation",
            title="Ausência de trilha de auditoria no banco",
            attack_scenario="Alterações sensíveis no banco não são registradas, impedindo responsabilização.",
            likelihood="Low",
            impact="Medium",
            risk_score=6,
            cwe_ids=["CWE-778"],
            mitigations=[Mitigation(description="Habilitar logging de auditoria imutável.", type="Detective", refs=["ASVS V7.1.1"])],
            provenance=provenance,  # type: ignore[arg-type]
        ),
    ]
    return ThreatModel(
        system_name=system_name,
        components=components,
        edges=edges,
        threats=threats,
        meta={"mock": True, "provenance": provenance},
    )
