"""Ingestão do MITRE D3FEND → `catalog/d3fend.json` (contramedidas defensivas + ATT&CK↔D3FEND).

Usa o *full mappings* (SPARQL JSON) do D3FEND, que liga cada técnica defensiva às técnicas ATT&CK
que ela contraria. Cada técnica D3FEND vira `Control`... não — vira `D3FEND`
{id: 'D3F-CredentialHardening', name, url} com rels `COUNTERS → ATTACK`. É o que fecha a cadeia
CWE→CAPEC→ATT&CK→**D3FEND** (defesa).
"""

from __future__ import annotations

import json
import sys

from app.argus.knowledge.ingest import common

D3FEND_MAP_URL = "https://d3fend.mitre.org/api/ontology/inference/d3fend-full-mappings.json"


def parse(doc: dict) -> list[dict]:
    by: dict[str, dict] = {}
    attacks: dict[str, set[str]] = {}
    for row in doc.get("results", {}).get("bindings", []):
        off = row.get("off_tech_id", {}).get("value")
        deft = row.get("def_tech", {}).get("value", "")
        label = row.get("def_tech_label", {}).get("value", "")
        if not off or not deft:
            continue
        frag = deft.rsplit("#", 1)[-1]  # 'CredentialHardening'
        did = f"D3F-{frag}"
        by.setdefault(did, {
            "id": did, "kind": "D3FEND", "name": label or frag,
            "url": f"https://d3fend.mitre.org/technique/d3f:{frag}/", "text": "", "stride": [], "rels": [],
        })
        attacks.setdefault(did, set()).add(off)
    for did, ent in by.items():
        ent["rels"] = [{"type": "COUNTERS", "target_kind": "ATTACK", "target_id": a} for a in sorted(attacks[did])]
    return list(by.values())


def run() -> int:
    doc = json.loads(common.fetch(D3FEND_MAP_URL, cache_name="d3fend_mappings.json", timeout=120))
    entities = parse(doc)
    out = common.save_normalized("d3fend", entities)
    print(f"D3FEND: {len(entities)} técnicas defensivas → {out}")
    return len(entities)


if __name__ == "__main__":
    sys.exit(0 if run() > 0 else 1)
