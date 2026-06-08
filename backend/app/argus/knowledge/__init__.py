"""Base de conhecimento ancorada (Fase 3) — catálogos de segurança + grafo de conhecimento.

Núcleo PORTÁTIL (sem dependência pesada): catálogos normalizados em JSON versionado
(`data/knowledge/normalized/`) carregados por um grafo em memória (`LocalKG`), com consulta
de subgrafo por (classe canônica, categoria STRIDE) e validação de IDs (anti-alucinação).

Neo4j (Cypher) e Chroma (RAG semântico) entram como adaptadores/realces nos incrementos 3.7–3.8,
atrás do mesmo contrato `KnowledgeStore`. Ver PLANO-IMPLEMENTACAO.md, Phase 3.
"""
