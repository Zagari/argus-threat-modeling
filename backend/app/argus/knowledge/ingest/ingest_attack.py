"""Ingestão do MITRE ATT&CK Enterprise (STIX) → `catalog/attack.json`.

Cada técnica (`attack-pattern` não revogada/depreciada) vira uma Entity {id: 'T1078', kind:
'ATTACK', name, url, text}. A ponte CAPEC→ATT&CK vem do próprio CAPEC (Taxonomy_Mappings),
tratada no `ingest_capec.py`.
"""

from __future__ import annotations

import json
import sys

from app.argus.knowledge.ingest import common

ATTACK_URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"


def parse(doc: dict) -> list[dict]:
    entities: list[dict] = []
    for o in doc.get("objects", []):
        if o.get("type") != "attack-pattern" or o.get("revoked") or o.get("x_mitre_deprecated"):
            continue
        tid = url = None
        for ref in o.get("external_references", []):
            if ref.get("source_name") == "mitre-attack" and ref.get("external_id"):
                tid, url = ref["external_id"], ref.get("url")
                break
        if not tid:
            continue
        entities.append({
            "id": tid, "kind": "ATTACK", "name": o.get("name", ""),
            "url": url or f"https://attack.mitre.org/techniques/{tid.replace('.', '/')}/",
            "text": common.clip(o.get("description", "")), "stride": [], "rels": [],
        })
    return entities


def run() -> int:
    doc = json.loads(common.fetch(ATTACK_URL, cache_name="enterprise-attack.json", timeout=120))
    entities = parse(doc)
    out = common.save_normalized("attack", entities)
    print(f"ATT&CK: {len(entities)} técnicas → {out}")
    return len(entities)


if __name__ == "__main__":
    sys.exit(0 if run() > 0 else 1)
