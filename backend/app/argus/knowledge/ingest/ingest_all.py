"""Orquestra a ingestão dos catálogos e valida contagens mínimas (idempotente).

    python -m app.argus.knowledge.ingest.ingest_all          # baixa CWE+CAPEC e normaliza
    python -m app.argus.knowledge.ingest.ingest_all --check  # só valida o que já existe

ASVS entra pelas sementes (14 capítulos); ATT&CK/D3FEND/NIST chegam no incremento 3.6.
"""

from __future__ import annotations

import sys

from app.argus.knowledge.ingest import (
    ingest_asvs,
    ingest_attack,
    ingest_capec,
    ingest_cwe,
    ingest_d3fend,
    ingest_nist,
)
from app.argus.knowledge.store import LocalKG

# Contagens mínimas esperadas (sanity-check dos catálogos).
MIN_COUNTS = {"CWE": 800, "CAPEC": 500, "ATTACK": 500, "D3FEND": 100, "Control": 300}


def run_check() -> int:
    counts: dict[str, int] = {}
    for e in LocalKG().iter_entities():
        counts[e.kind] = counts.get(e.kind, 0) + 1
    ok = True
    for kind, mn in MIN_COUNTS.items():
        n = counts.get(kind, 0)
        ok = ok and n >= mn
        print(f"{kind}: {n} (mín {mn}) {'OK' if n >= mn else 'FALTA'}")
    return 0 if ok else 1


def run_ingest() -> int:
    ingest_cwe.run()
    ingest_attack.run()   # antes do CAPEC (o CAPEC referencia técnicas ATT&CK)
    ingest_capec.run()
    ingest_asvs.run()
    ingest_nist.run()
    ingest_d3fend.run()
    return run_check()


if __name__ == "__main__":
    sys.exit(run_check() if "--check" in sys.argv[1:] else run_ingest())
