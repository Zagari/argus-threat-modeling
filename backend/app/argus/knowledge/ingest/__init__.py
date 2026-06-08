"""Ingestão dos catálogos de segurança → JSON normalizado (`data/knowledge/normalized/`).

Uso (manual/CI de geração; NÃO roda no app):
    python -m app.argus.knowledge.ingest.ingest_all          # baixa + normaliza
    python -m app.argus.knowledge.ingest.ingest_all --check  # valida contagens mínimas

Os fontes brutos vão para `data/knowledge/raw/` (gitignored); o normalizado é versionado.
"""
