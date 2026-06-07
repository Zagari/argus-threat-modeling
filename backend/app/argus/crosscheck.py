"""E2 — Cross-check de classificação via VLM.

Depois do detector (E1) e da fusão com OCR (E2a), alguns componentes ainda ficam incertos:
caixas genéricas/serviços sem sinônimo de rótulo (ex.: ``REST``/``SOAP``), legendas mal
lidas pelo OCR, ou detecções de baixa confiança. O VLM relê o diagrama de forma holística e
propõe a classe canônica de cada componente; adotamos a sugestão **apenas para os
componentes incertos** (confiança visual baixa), preservando as detecções fortes do E1.

Roda em qualquer ambiente (só precisa da chave do LLM); em modo mock, é no-op.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.config import get_config
from app.llm import provider
from app.schemas import Component
from app.taxonomy import CANONICAL_CLASSES, CANONICAL_ELEMENT_TYPE

_SYSTEM = (
    "Você é um especialista em arquiteturas de nuvem (AWS/Azure/GCP) que classifica "
    "componentes de diagramas em classes canônicas. Responda sempre em português."
)

_PROMPT = """Recebe a imagem de um diagrama de arquitetura e a lista de componentes já \
detectados (com id, classe atual, posição e rótulo lido). Para CADA id, indique a CLASSE \
CANÔNICA correta, escolhida EXCLUSIVAMENTE desta lista:
{classes}

Componentes (id | classe atual | bbox [x,y,w,h] normalizado | rótulo):
{components}

Regras:
- Escolha a classe da lista que melhor descreve o componente naquela posição (use o ícone \
e o texto próximo).
- Se a classe atual já estiver correta, repita-a.
- Use os MESMOS ids; não invente componentes.
- Responda para TODOS os ids."""


class _Vote(BaseModel):
    id: str
    canonical: str


class _Votes(BaseModel):
    components: list[_Vote] = Field(default_factory=list)


def verify(image_bytes: bytes, components: list[Component], *, mime: str = "image/jpeg") -> list[Component]:
    """Corrige a classe dos componentes INCERTOS usando o VLM. Detecções fortes ficam."""
    cfg = get_config()
    if cfg.mock or not components:
        return components

    conf_thr = float(os.getenv("ARGUS_CROSSCHECK_CONF", "0.75"))
    valid = set(CANONICAL_CLASSES)
    lines = "\n".join(
        f"- {c.id} | {c.canonical} | {[round(v, 2) for v in (c.bbox or [])]} | {c.label or '-'}"
        for c in components
    )
    prompt = _PROMPT.format(classes=", ".join(CANONICAL_CLASSES), components=lines)
    votes: _Votes = provider.vision(  # type: ignore[assignment]
        image_bytes, prompt, response_model=_Votes, mime=mime, system=_SYSTEM, temperature=0.0
    )
    vote_map = {v.id: v.canonical for v in votes.components if v.canonical in valid}

    out: list[Component] = []
    for c in components:
        new = c.model_copy()
        vc = vote_map.get(c.id)
        cur_conf = c.confidence if c.confidence is not None else 1.0
        # adota o VLM só quando o componente estava incerto (não sobrescreve detecção forte)
        if vc and vc != c.canonical and cur_conf < conf_thr:
            new.canonical = vc
            new.element_type = CANONICAL_ELEMENT_TYPE.get(vc, new.element_type)  # type: ignore[assignment]
        out.append(new)
    return out
