"""CVEs reais por componente — lê o cache versionado `catalog/cve_by_class.json`.

O cache é populado OFFLINE por `ingest/warm_cve.py` (NVD 2.0). O app **não** chama a NVD ao
vivo: zero latência/flakiness, roda em CI/HF Spaces sem rede. Os CVEs são reais (vêm da NVD),
então o ARGUS nunca "inventa" CVE — ele os recupera. `is_known` permite validar um id citado
contra o que conhecemos (uso na Fase 5; um id ausente do cache é "não verificado", não "falso").
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.schemas import Component

_CACHE = Path(__file__).resolve().parent / "catalog" / "cve_by_class.json"


@lru_cache(maxsize=1)
def _by_class() -> dict[str, list[dict]]:
    try:
        return json.loads(_CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=1)
def _known_ids() -> frozenset[str]:
    return frozenset(c["id"].upper() for lst in _by_class().values() for c in lst)


def cves_for_component(component: Component, limit: int = 5) -> list[dict]:
    """CVEs reais (id, cvss, severity, url, cpe) para a classe do componente — já ordenados."""
    return _by_class().get(component.canonical, [])[:limit]


def is_known(cve_id: str) -> bool:
    """True se o CVE consta do cache (real conhecido). Ausência ≠ inexistente (cache é parcial)."""
    return cve_id.upper() in _known_ids()


def total_known() -> int:
    return len(_known_ids())
