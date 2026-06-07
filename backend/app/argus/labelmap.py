"""E2 — Mapa de rótulos-texto → classe canônica (caminho por OCR).

Lê os sinônimos de rótulo (`labels:`) do `training/taxonomy/mapeamento.yaml` (a fonte
única de verdade da taxonomia) e classifica um texto livre na classe canônica. É o que dá
o caráter agnóstico: um diagrama genérico/whiteboard ou de qualquer nuvem por NOME é
coberto pelo texto, independentemente do glifo.

Resolução do caminho do YAML (em ordem): env `ARGUS_MAPEAMENTO` → cópia ao lado deste
módulo → `training/taxonomy/mapeamento.yaml` na raiz do repo. Se nada for encontrado,
`match_label` simplesmente retorna None (degrada sem quebrar).
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve()
_CANDIDATES = [
    _HERE.parent / "mapeamento.yaml",                                  # cópia local (opcional)
    _HERE.parents[3] / "training" / "taxonomy" / "mapeamento.yaml",    # repo: argus/training/...
]


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text.lower()).split())


def _resolve_path() -> Path | None:
    env = os.getenv("ARGUS_MAPEAMENTO")
    if env:
        p = Path(env)
        return p if p.exists() else None
    for c in _CANDIDATES:
        if c.exists():
            return c
    return None


@lru_cache(maxsize=1)
def _load_labels() -> dict[str, list[str]]:
    path = _resolve_path()
    if not path:
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, list[str]] = {}
    for name, spec in (data.get("classes") or {}).items():
        out[name] = [_normalize(s) for s in (spec.get("labels") or []) if s]
    return out


def available() -> bool:
    return bool(_load_labels())


def match_label(text: str) -> str | None:
    """Classe canônica para um texto livre (ou None). Vence o sinônimo mais específico.

    Casa apenas quando o **sinônimo aparece dentro do rótulo** (`ns in norm`). O sentido
    inverso (rótulo curto contido num sinônimo longo) gera falsos positivos com fragmentos
    do OCR (ex.: ``Amazon`` casando ``amazon mq``), por isso é evitado.
    """
    norm = _normalize(text)
    if not norm:
        return None
    best: tuple[int, str] | None = None
    for cls, syns in _load_labels().items():
        for ns in syns:
            if ns and ns in norm and (best is None or len(ns) > best[0]):
                best = (len(ns), cls)
    return best[1] if best else None
