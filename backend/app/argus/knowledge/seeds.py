"""Mapeamentos-semente STRIDE→CWE e STRIDE→ASVS (a espinha dorsal determinística).

São relações *curadas* e estáveis (Microsoft/Shostack + Honkaranta et al.; STRIDE-vs-ASVS),
com IDs e nomes REAIS — garantem que `subgraph(classe, STRIDE)` sempre tenha âncoras citáveis,
mesmo antes de baixar os catálogos completos (CWE/CAPEC). O catálogo completo (ingest) apenas
*sobrepõe* nomes/urls e habilita a validação de QUALQUER id citado (não só os da semente).

As relações CWE↔CAPEC vêm do próprio catálogo CAPEC (`Related_Weaknesses`), não daqui.
"""

from __future__ import annotations

# STRIDE → CWEs aplicáveis (IDs reais; mapeamento canônico consolidado).
STRIDE_TO_CWE: dict[str, list[str]] = {
    "Spoofing": ["CWE-287", "CWE-290", "CWE-306", "CWE-384", "CWE-345"],
    "Tampering": ["CWE-20", "CWE-79", "CWE-89", "CWE-345", "CWE-494", "CWE-565", "CWE-639"],
    "Repudiation": ["CWE-778", "CWE-223", "CWE-117", "CWE-532"],
    "Information Disclosure": ["CWE-200", "CWE-311", "CWE-319", "CWE-359", "CWE-532"],
    "Denial of Service": ["CWE-400", "CWE-770", "CWE-405"],
    "Elevation of Privilege": ["CWE-269", "CWE-862", "CWE-863", "CWE-250", "CWE-732"],
}

# Nomes reais dos CWEs da semente (para citação sem depender do catálogo completo).
CWE_NAMES: dict[str, str] = {
    "CWE-20": "Improper Input Validation",
    "CWE-79": "Improper Neutralization of Input During Web Page Generation (XSS)",
    "CWE-89": "Improper Neutralization of Special Elements used in an SQL Command (SQLi)",
    "CWE-117": "Improper Output Neutralization for Logs",
    "CWE-200": "Exposure of Sensitive Information to an Unauthorized Actor",
    "CWE-223": "Omission of Security-relevant Information",
    "CWE-250": "Execution with Unnecessary Privileges",
    "CWE-269": "Improper Privilege Management",
    "CWE-287": "Improper Authentication",
    "CWE-290": "Authentication Bypass by Spoofing",
    "CWE-306": "Missing Authentication for Critical Function",
    "CWE-311": "Missing Encryption of Sensitive Data",
    "CWE-319": "Cleartext Transmission of Sensitive Information",
    "CWE-345": "Insufficient Verification of Data Authenticity",
    "CWE-359": "Exposure of Private Personal Information to an Unauthorized Actor",
    "CWE-384": "Session Fixation",
    "CWE-400": "Uncontrolled Resource Consumption",
    "CWE-405": "Asymmetric Resource Consumption (Amplification)",
    "CWE-494": "Download of Code Without Integrity Check",
    "CWE-532": "Insertion of Sensitive Information into Log File",
    "CWE-565": "Reliance on Cookies without Validation and Integrity Checking",
    "CWE-639": "Authorization Bypass Through User-Controlled Key",
    "CWE-732": "Incorrect Permission Assignment for Critical Resource",
    "CWE-770": "Allocation of Resources Without Limits or Throttling",
    "CWE-778": "Insufficient Logging",
    "CWE-862": "Missing Authorization",
    "CWE-863": "Incorrect Authorization",
}

# Capítulos do OWASP ASVS 4.0 (id → nome). Controles citáveis em nível de capítulo;
# o ingest do ASVS (3.1+) acrescenta os requisitos finos (V2.1.1 etc.) para validação.
ASVS_CHAPTERS: dict[str, str] = {
    "ASVS-V1": "Architecture, Design and Threat Modeling",
    "ASVS-V2": "Authentication",
    "ASVS-V3": "Session Management",
    "ASVS-V4": "Access Control",
    "ASVS-V5": "Validation, Sanitization and Encoding",
    "ASVS-V6": "Stored Cryptography",
    "ASVS-V7": "Error Handling and Logging",
    "ASVS-V8": "Data Protection",
    "ASVS-V9": "Communication",
    "ASVS-V10": "Malicious Code",
    "ASVS-V11": "Business Logic",
    "ASVS-V12": "Files and Resources",
    "ASVS-V13": "API and Web Service",
    "ASVS-V14": "Configuration",
}

# STRIDE → capítulos ASVS (contramedidas) — STRIDE-vs-ASVS consolidado.
STRIDE_TO_ASVS: dict[str, list[str]] = {
    "Spoofing": ["ASVS-V2", "ASVS-V3"],
    "Tampering": ["ASVS-V5", "ASVS-V10", "ASVS-V11"],
    "Repudiation": ["ASVS-V7"],
    "Information Disclosure": ["ASVS-V6", "ASVS-V8", "ASVS-V9"],
    "Denial of Service": ["ASVS-V11", "ASVS-V13"],
    "Elevation of Privilege": ["ASVS-V4"],
}


def cwe_url(cwe_id: str) -> str:
    return f"https://cwe.mitre.org/data/definitions/{cwe_id.removeprefix('CWE-')}.html"


def capec_url(capec_id: str) -> str:
    return f"https://capec.mitre.org/data/definitions/{capec_id.removeprefix('CAPEC-')}.html"


def asvs_url(_chapter_id: str) -> str:
    return "https://owasp.org/www-project-application-security-verification-standard/"
