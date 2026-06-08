"""Ingestão do catálogo CWE (XML) → `normalized/cwe.json`.

Cada `<Weakness>` vira uma Entity {id: 'CWE-<n>', kind: 'CWE', name, url, text}. O índice
completo (todas as fraquezas) é o que habilita a validação de QUALQUER CWE citado.
"""

from __future__ import annotations

import io
import sys
import xml.etree.ElementTree as ET
import zipfile

from app.argus.knowledge.ingest import common
from app.argus.knowledge.seeds import cwe_url

CWE_ZIP_URL = "https://cwe.mitre.org/data/xml/cwec_latest.xml.zip"


def _xml_bytes() -> bytes:
    raw = common.fetch(CWE_ZIP_URL, cache_name="cwec_latest.xml.zip")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name = next(n for n in z.namelist() if n.endswith(".xml"))
        return z.read(name)


def parse(xml: bytes) -> list[dict]:
    root = ET.fromstring(xml)
    entities: list[dict] = []
    for w in root.findall(".//{*}Weakness"):  # findall suporta '{*}' (qualquer namespace); iter() não
        wid = w.get("ID")
        if not wid:
            continue
        desc = w.find("{*}Description")
        text = common.clip("".join(desc.itertext()) if desc is not None else "")
        entities.append({
            "id": f"CWE-{wid}",
            "kind": "CWE",
            "name": w.get("Name", ""),
            "url": cwe_url(wid),
            "text": text,
            "stride": [],
            "rels": [],
        })
    return entities


def run() -> int:
    entities = parse(_xml_bytes())
    out = common.save_normalized("cwe", entities)
    print(f"CWE: {len(entities)} fraquezas → {out}")
    return len(entities)


if __name__ == "__main__":
    sys.exit(0 if run() > 0 else 1)
