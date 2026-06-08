"""Warming OFFLINE do cache de CVE: `classes.<classe>.cpe_hints` → NVD 2.0 → `catalog/cve_by_class.json`.

    python -m app.argus.knowledge.ingest.warm_cve

Respeita o rate-limit da NVD (~5 req/30s sem chave) com pausa entre chamadas. O resultado
(por classe canônica, top-N por CVSS) é versionado DENTRO do pacote → segue a imagem; o app
(`cve.py`) só LÊ o cache, nunca chama a NVD ao vivo. Os CVEs são reais (vêm da NVD).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import yaml

from app.argus.knowledge.ingest import common

NVD = "https://services.nvd.nist.gov/rest/json/cves/2.0"
TOP_N = 8
RESULTS_PER_CPE = 40
SLEEP_S = 7.0  # entre chamadas (rate-limit NVD sem chave)


def _mapeamento_classes() -> dict:
    # mapeamento.yaml fica em training/ (disponível em dev/CI; NÃO vai para a imagem).
    p = Path(__file__).resolve().parents[5] / "training" / "taxonomy" / "mapeamento.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))["classes"]


def _cvss(cve: dict) -> tuple[float | None, str]:
    metrics = cve.get("metrics", {})
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        if metrics.get(key):
            entry = metrics[key][0]
            data = entry.get("cvssData", {})
            return data.get("baseScore"), data.get("baseSeverity") or entry.get("baseSeverity") or ""
    return None, ""


def _cves_for_cpe(cpe: str) -> list[dict]:
    safe = cpe.replace(":", "_").replace("*", "x").replace("/", "_")
    raw = common.fetch(
        f"{NVD}?virtualMatchString={cpe}&resultsPerPage={RESULTS_PER_CPE}",
        cache_name=f"nvd_{safe}.json",
        timeout=45,
    )
    doc = json.loads(raw)
    out: list[dict] = []
    for v in doc.get("vulnerabilities", []):
        cve = v["cve"]
        cid = cve["id"]
        score, sev = _cvss(cve)
        desc = next((d.get("value", "") for d in cve.get("descriptions", []) if d.get("lang") == "en"), "")
        out.append({
            "id": cid, "cvss": score, "severity": sev, "cpe": cpe,
            "url": f"https://nvd.nist.gov/vuln/detail/{cid}", "text": common.clip(desc, 160),
        })
    return out


def run() -> int:
    classes = _mapeamento_classes()
    by_class: dict[str, list[dict]] = {}
    calls = 0
    for cls, attrs in classes.items():
        hints = attrs.get("cpe_hints") or []
        if not hints:
            continue
        merged: dict[str, dict] = {}
        for cpe in hints:
            if calls:
                time.sleep(SLEEP_S)
            calls += 1
            try:
                for c in _cves_for_cpe(cpe):
                    prev = merged.get(c["id"])
                    if prev is None or (c["cvss"] or 0) > (prev["cvss"] or 0):
                        merged[c["id"]] = c
            except Exception as e:  # noqa: BLE001
                print(f"  ! {cpe}: {e}")
        # ordena por (CVSS, ano do CVE) desc → severos e recentes primeiro
        def _key(c: dict) -> tuple[float, int]:
            parts = c["id"].split("-")
            year = int(parts[1]) if len(parts) > 2 and parts[1].isdigit() else 0
            return (c["cvss"] or 0.0, year)

        ranked = sorted(merged.values(), key=_key, reverse=True)[:TOP_N]
        by_class[cls] = ranked
        print(f"  {cls}: {len(ranked)} CVEs (de {len(hints)} CPE)")

    out = common.NORMALIZED_DIR / "cve_by_class.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(by_class, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(v) for v in by_class.values())
    print(f"→ {out} ({total} CVEs em {len(by_class)} classes; {calls} chamadas NVD)")
    return len(by_class)


if __name__ == "__main__":
    sys.exit(0 if run() > 0 else 1)
