"""Ingestão dos requisitos finos do OWASP ASVS 4.0.3 → `catalog/asvs.json`.

Cada requisito (ex.: `V2.1.1`) vira um `Control` {id: 'ASVS-V2.1.1', name: texto, url: capítulo no
GitHub, rels: ADDRESSES→CWE}. Habilita citar o **controle exato** (não só o capítulo) no E5/PDF/subgrafo.
Fonte: o `.flat.json` oficial (um registro por requisito). Os capítulos (ASVS-V1..V14) seguem vindo das
sementes; aqui entram os requisitos detalhados.
"""

from __future__ import annotations

import json
import re
import sys

from app.argus.knowledge.ingest import common
from app.argus.knowledge.seeds import asvs_chapter_url

ASVS_FLAT_URL = (
    "https://raw.githubusercontent.com/OWASP/ASVS/v4.0.3/4.0/docs_en/"
    "OWASP%20Application%20Security%20Verification%20Standard%204.0.3-en.flat.json"
)

_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")  # [C1](url) → C1


def _clean(text: str) -> str:
    return common.clip(_MD_LINK.sub(r"\1", text or ""), 240)


def _cwe_rels(raw: str) -> list[dict]:
    return [{"type": "ADDRESSES", "target_kind": "CWE", "target_id": f"CWE-{n}"} for n in re.findall(r"\d+", raw or "")]


def parse(doc: dict) -> list[dict]:
    entities: list[dict] = []
    for r in doc.get("requirements", []):
        rid = r.get("req_id")
        if not rid:
            continue
        entities.append({
            "id": f"ASVS-{rid}",
            "kind": "Control",
            "name": _clean(r.get("req_description", "")),
            "url": asvs_chapter_url(r.get("chapter_id", "")),
            "text": f"{r.get('chapter_name', '')} · {r.get('section_name', '')}".strip(" ·"),
            "stride": [],
            "rels": _cwe_rels(r.get("cwe", "")),
        })
    return entities


def run() -> int:
    doc = json.loads(common.fetch(ASVS_FLAT_URL, cache_name="asvs_flat.json"))
    entities = parse(doc)
    out = common.save_normalized("asvs", entities)
    print(f"ASVS: {len(entities)} requisitos → {out}")
    return len(entities)


if __name__ == "__main__":
    sys.exit(0 if run() > 0 else 1)
