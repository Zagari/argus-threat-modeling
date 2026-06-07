"""E2 — Extração de topologia (setas → grafo) via VLM (primário).

Em vez de tentar detectar setas por visão computacional clássica (frágil em diagramas
reais — conectores ortogonais, tracejados, cruzamentos), damos ao VLM a imagem + a lista
de componentes já detectados (com IDs estáveis) e pedimos as arestas DIRIGIDAS. A CV
clássica pode entrar depois como reforço; o grafo é editável na UI (humano no loop).

Não marca `crosses_boundary` — isso é responsabilidade do E3 (DFD).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.config import get_config
from app.llm import provider
from app.schemas import Component, Edge

_SYSTEM = (
    "Você é um especialista em ler diagramas de arquitetura de software/nuvem e extrair a "
    "topologia (quem se conecta a quem). Responda sempre em português."
)

_PROMPT = """Você recebe a imagem de um diagrama de arquitetura e a lista de componentes já \
detectados nele (com IDs). Identifique as SETAS/CONEXÕES entre os componentes e devolva-as \
como arestas DIRIGIDAS, usando EXATAMENTE os IDs fornecidos.

Componentes detectados:
{components}

Regras:
- Use apenas os IDs listados acima em `source` e `target`.
- A direção segue a seta (origem -> destino). Sem seta explícita, infira pelo fluxo de \
dados típico (ex.: usuário -> gateway -> serviço -> banco).
- Não invente componentes nem IDs; ignore conexões duvidosas.
- `label` (opcional): protocolo/anotação da seta, se visível (ex.: HTTPS, SQL).
- NÃO preencha `crosses_boundary` (será calculado depois)."""


class _EdgeList(BaseModel):
    edges: list[Edge] = Field(default_factory=list)


def _mock_edges(components: list[Component]) -> list[Edge]:
    ids = [c.id for c in components if c.element_type != "TrustBoundary"]
    return [Edge(source=ids[i], target=ids[i + 1], label="mock") for i in range(len(ids) - 1)]


def extract(image_bytes: bytes, components: list[Component], *, mime: str = "image/jpeg") -> list[Edge]:
    """Retorna as arestas dirigidas entre os componentes, lidas do diagrama pelo VLM."""
    cfg = get_config()
    valid = {c.id for c in components}
    if cfg.mock:
        return _mock_edges(components)
    if len(components) < 2:
        return []

    comp_lines = "\n".join(
        f"- {c.id}: {c.canonical}" + (f' (rótulo: "{c.label}")' if c.label else "")
        for c in components
    )
    prompt = _PROMPT.format(components=comp_lines)
    result: _EdgeList = provider.vision(  # type: ignore[assignment]
        image_bytes, prompt, response_model=_EdgeList, mime=mime, system=_SYSTEM, temperature=0.1
    )

    edges: list[Edge] = []
    seen: set[tuple[str, str]] = set()
    for e in result.edges:
        key = (e.source, e.target)
        if e.source in valid and e.target in valid and e.source != e.target and key not in seen:
            seen.add(key)
            edges.append(e)
    return edges
