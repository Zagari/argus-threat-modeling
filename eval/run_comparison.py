"""CLI do estudo comparativo (Fase 5) — roda no Mac (Cíclope; ARGUS se houver ML) ou no servidor.

Exemplos:
    python eval/run_comparison.py                      # 2 Figuras, N=3, os dois sistemas
    python eval/run_comparison.py --n 3 --systems ciclope
    python eval/run_comparison.py --images data/gold/figura-1-arquitetura-1.jpg --force

Saídas: `eval/results/<imagem>/<sistema>/run-*.json` (cache) + `eval/results/summary.{json,md}`.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # permite `import harness, metrics`
import harness  # noqa: E402
import metrics  # noqa: E402


def _resolve_images(patterns: list[str] | None) -> list[Path]:
    if not patterns:
        return harness.default_images()
    out: list[Path] = []
    for pat in patterns:
        out.extend(Path(p) for p in sorted(glob.glob(pat)))
    return [p for p in out if p.exists()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Estudo comparativo Cíclope × ARGUS (Fase 5).")
    ap.add_argument("--images", nargs="*", help="caminhos/globs de imagens (default: data/gold/figura-*)")
    ap.add_argument("--n", type=int, default=3, help="execuções por (imagem × sistema) [3]")
    ap.add_argument("--systems", default="ciclope,argus", help="csv: ciclope,argus")
    ap.add_argument("--force", action="store_true", help="ignora o cache e re-executa")
    ap.add_argument("--sleep", type=float, default=0.0, help="pausa (s) entre chamadas reais (rate-limit)")
    args = ap.parse_args(argv)

    images = _resolve_images(args.images)
    systems = tuple(s.strip() for s in args.systems.split(",") if s.strip())
    print(f"▶ {len(images)} imagem(ns) × {systems} × N={args.n}\n")

    runs = harness.run_matrix(images, systems=systems, n=args.n, force=args.force, sleep_s=args.sleep)
    measured = harness.measure_runs(runs)
    summary = metrics.summarize(measured)

    table = metrics.format_table(summary)
    print("\n" + table + "\n")

    results = harness.RESULTS_DIR
    results.mkdir(parents=True, exist_ok=True)
    (results / "summary.md").write_text(table + "\n", encoding="utf-8")
    # chaves de tupla → string "imagem::sistema" p/ serializar em JSON
    payload = {f"{img}::{sys_}": agg for (img, sys_), agg in summary.items()}
    (results / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    errors = [r for r in runs if "error" in r]
    if errors:
        print(f"⚠️  {len(errors)} execução(ões) falharam (veja acima). Tabela cobre as que rodaram.")
    print(f"✓ resultados em {results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
