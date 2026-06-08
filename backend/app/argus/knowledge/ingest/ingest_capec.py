"""Ingestão do catálogo CAPEC (XML) → `normalized/capec.json`.

Cada `<Attack_Pattern>` vira uma Entity {id: 'CAPEC-<n>', kind: 'CAPEC', name, url, text, rels}.
As relações `Related_Weaknesses` viram `TARGETS → CWE` (é a ponte CWE↔CAPEC que o `LocalKG`
usa para montar o subgrafo).
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET

from app.argus.knowledge.ingest import common
from app.argus.knowledge.seeds import capec_url

CAPEC_XML_URL = "https://capec.mitre.org/data/xml/capec_latest.xml"


def parse(xml: bytes) -> list[dict]:
    root = ET.fromstring(xml)
    entities: list[dict] = []
    for ap in root.findall(".//{*}Attack_Pattern"):  # findall suporta '{*}'; iter() não
        cid = ap.get("ID")
        if not cid:
            continue
        desc = ap.find("{*}Description")
        rels: list[dict] = []
        for rw in ap.findall(".//{*}Related_Weakness"):
            cwe = rw.get("CWE_ID")
            if cwe:
                rels.append({"type": "TARGETS", "target_kind": "CWE", "target_id": f"CWE-{cwe}"})
        entities.append({
            "id": f"CAPEC-{cid}",
            "kind": "CAPEC",
            "name": ap.get("Name", ""),
            "url": capec_url(cid),
            "text": common.clip("".join(desc.itertext()) if desc is not None else ""),
            "stride": [],
            "rels": rels,
        })
    return entities


def run() -> int:
    entities = parse(common.fetch(CAPEC_XML_URL, cache_name="capec_latest.xml"))
    out = common.save_normalized("capec", entities)
    print(f"CAPEC: {len(entities)} padrões → {out}")
    return len(entities)


if __name__ == "__main__":
    sys.exit(0 if run() > 0 else 1)
