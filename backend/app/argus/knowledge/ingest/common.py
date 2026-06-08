"""Utilitários de ingestão: download (com cache em raw/), e escrita do normalizado."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

_KNOWLEDGE = Path(__file__).resolve().parents[5] / "data" / "knowledge"
RAW_DIR = _KNOWLEDGE / "raw"
NORMALIZED_DIR = _KNOWLEDGE / "normalized"


def fetch(url: str, *, cache_name: str, timeout: float = 120.0) -> bytes:
    """Baixa `url` (ou usa o cache em `raw/cache_name`). Retorna os bytes."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cached = RAW_DIR / cache_name
    if cached.exists() and cached.stat().st_size > 0:
        return cached.read_bytes()
    with httpx.Client(timeout=timeout, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
        cached.write_bytes(r.content)
        return r.content


def save_normalized(name: str, entities: list[dict]) -> Path:
    """Grava `normalized/<name>.json` (ordenado por id, p/ diffs estáveis)."""
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    out = NORMALIZED_DIR / f"{name}.json"
    entities = sorted(entities, key=lambda e: _sort_key(e.get("id", "")))
    out.write_text(json.dumps(entities, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def _sort_key(eid: str) -> tuple[str, int, str]:
    """Ordena 'CWE-89' como (prefixo, número, '') p/ ordem numérica natural."""
    prefix, _, num = eid.partition("-")
    return (prefix, int(num) if num.isdigit() else 0, eid)


def clip(text: str | None, n: int = 400) -> str:
    """Texto de descrição compacto (1 linha, truncado) p/ manter o JSON enxuto."""
    if not text:
        return ""
    t = " ".join(text.split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"
