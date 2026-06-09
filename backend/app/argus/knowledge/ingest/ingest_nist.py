"""Ingestão do NIST SP 800-53 Rev.5 (OSCAL JSON) → `catalog/nist80053.json`.

Controles-base por família (ex.: `AC-2` "Account Management") como `Control`
{id: 'NIST-AC-2', name, url}. O elo STRIDE→NIST é um seed curado (controles reais);
aqui entra o catálogo para nome/link/validação. Enhancements (AC-2.1) ficam de fora (base é suficiente).
"""

from __future__ import annotations

import json
import sys

from app.argus.knowledge.ingest import common

NIST_URL = (
    "https://raw.githubusercontent.com/usnistgov/oscal-content/main/"
    "nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json"
)


def parse(doc: dict) -> list[dict]:
    entities: list[dict] = []
    for g in doc.get("catalog", {}).get("groups", []):
        fam = g.get("id", "")  # 'ac'
        for c in g.get("controls", []):
            cid = c.get("id", "")  # 'ac-2'
            if not cid:
                continue
            entities.append({
                "id": f"NIST-{cid.upper()}", "kind": "Control", "name": c.get("title", ""),
                "url": f"https://csf.tools/reference/nist-sp-800-53/r5/{fam}/{cid}/",
                "text": "NIST SP 800-53 Rev.5", "stride": [], "rels": [],
            })
    return entities


def run() -> int:
    doc = json.loads(common.fetch(NIST_URL, cache_name="nist80053_rev5.json", timeout=120))
    entities = parse(doc)
    out = common.save_normalized("nist80053", entities)
    print(f"NIST 800-53: {len(entities)} controles-base → {out}")
    return len(entities)


if __name__ == "__main__":
    sys.exit(0 if run() > 0 else 1)
