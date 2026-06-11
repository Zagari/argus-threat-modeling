"""Endpoint do painel comparativo (Fase 4, frente 3) — diff Cíclope × ARGUS.

Recebe os dois `ThreatModel` (o frontend roda as análises em paralelo via SSE) e devolve o
resumo comparativo + diff. Não roda os pipelines aqui (evita o teto de latência do proxy).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.compare import diff
from app.schemas import ThreatModel

router = APIRouter(prefix="/compare", tags=["compare"])


class _Pair(BaseModel):
    ciclope: ThreatModel
    argus: ThreatModel


@router.post("/diff")
def compare_diff(pair: _Pair) -> dict:
    return diff(pair.ciclope, pair.argus)
