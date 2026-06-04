"""Taxonomia canônica (agnóstica de nuvem) + matriz STRIDE-per-element.

Versão mínima da Fase 0 — o `mapeamento.yaml` completo (sinônimos AWS/Azure de
ícone e de rótulo) chega na Fase 1. Aqui ficam as classes canônicas, seu tipo
DFD primário e a matriz canônica de STRIDE por elemento (Microsoft/Shostack),
que restringe o que o LLM pode propor. Ver PROPOSTA-TECNICA.md §5.1 e §14.
"""

from __future__ import annotations

# classe canônica -> tipo DFD primário
CANONICAL_ELEMENT_TYPE: dict[str, str] = {
    "actor/user": "ExternalEntity",
    "edge_security": "Process",
    "api_gateway": "Process",
    "load_balancer": "Process",
    "compute": "Process",
    "serverless_fn": "Process",
    "app_service": "Process",
    "database_sql": "DataStore",
    "database_nosql": "DataStore",
    "cache": "DataStore",
    "object_storage": "DataStore",
    "file_storage": "DataStore",
    "message_queue": "DataStore",
    "cdn": "Process",
    "identity": "Process",
    "secrets": "DataStore",
    "search": "DataStore",
    "monitoring": "DataStore",
    "email_notify": "Process",
    "backend_external": "ExternalEntity",
    "trust_boundary": "TrustBoundary",
}

CANONICAL_CLASSES: list[str] = list(CANONICAL_ELEMENT_TYPE.keys())

# Matriz canônica: categorias STRIDE aplicáveis por tipo de elemento DFD.
STRIDE_PER_ELEMENT: dict[str, list[str]] = {
    "ExternalEntity": ["Spoofing", "Repudiation"],
    "DataFlow": ["Tampering", "Information Disclosure", "Denial of Service"],
    "DataStore": ["Tampering", "Repudiation", "Information Disclosure", "Denial of Service"],
    "Process": [
        "Spoofing",
        "Tampering",
        "Repudiation",
        "Information Disclosure",
        "Denial of Service",
        "Elevation of Privilege",
    ],
    "TrustBoundary": [],  # gatilho: analisar os Data Flows que a cruzam
}


def applicable_categories(element_type: str) -> list[str]:
    return STRIDE_PER_ELEMENT.get(element_type, [])
