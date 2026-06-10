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

# Sinais de relevância para o rank (3.10): likelihood domina, severidade desempata, abstração afina.
_LIKELIHOOD = {"High": 3, "Medium": 2, "Low": 1}
_SEVERITY = {"Very High": 5, "High": 4, "Medium": 3, "Low": 2, "Very Low": 1}
_ABSTRACTION = {"Standard": 2, "Meta": 1, "Detailed": 0}


def _text(ap: ET.Element, tag: str) -> str:
    el = ap.find(f"{{*}}{tag}")
    return (el.text or "").strip() if el is not None and el.text else ""


def _rank(ap: ET.Element) -> int:
    """Score intrínseco (maior = mais relevante): likelihood×100 + severidade×10 + abstração."""
    lk = _LIKELIHOOD.get(_text(ap, "Likelihood_Of_Attack"), 0)
    sv = _SEVERITY.get(_text(ap, "Typical_Severity"), 0)
    ab = _ABSTRACTION.get(ap.get("Abstraction", ""), 0)
    return lk * 100 + sv * 10 + ab


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
        # Mapeamento de taxonomia para o MITRE ATT&CK (Entry_ID = número da técnica).
        for tm in ap.findall(".//{*}Taxonomy_Mapping"):
            if (tm.get("Taxonomy_Name") or "").upper() == "ATTACK":
                ent = tm.find("{*}Entry_ID")
                tid = (ent.text or "").strip() if ent is not None else ""
                if tid:
                    rels.append({"type": "MAPS_TO", "target_kind": "ATTACK", "target_id": f"T{tid}"})
        entities.append({
            "id": f"CAPEC-{cid}",
            "kind": "CAPEC",
            "name": ap.get("Name", ""),
            "url": capec_url(cid),
            "text": common.clip("".join(desc.itertext()) if desc is not None else ""),
            "rank": _rank(ap),
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
