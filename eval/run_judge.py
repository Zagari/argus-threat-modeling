"""Roda o LLM-as-judge (Fase 5, Lote 5.2) sobre os relatórios já gerados pelo 5.1.

Lê os `ThreatModel` cacheados em `eval/results/<imagem>/<sistema>/run-*.json`, julga cada um
**pointwise** (nota 0–100) e faz o **pairwise** Cíclope×ARGUS por figura (dupla ordem anti-viés),
com **cache** dos vereditos (`judge-*.json`, `judge-pairwise.json`) — o juiz é caro, reruns não
re-gastam. Agrega as N execuções em média±desvio e escreve `eval/results/judge_summary.{json,md}`.

Uso: `.venv-ml/bin/python eval/run_judge.py [--force] [--pointwise-only]`
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402  (RESULTS_DIR + path do backend/.env via app.config)
import judge  # noqa: E402
import metrics  # noqa: E402

# garante o carregamento do .env (JUDGE_*) — harness já põe backend no path
import app.config  # noqa: E402,F401


def load_cached(results_dir: Path) -> dict[str, dict[str, list[dict]]]:
    """{ imagem: { sistema: [tm por run] } } a partir dos caches do 5.1."""
    out: dict[str, dict[str, list[dict]]] = {}
    for img_dir in sorted(d for d in results_dir.iterdir() if d.is_dir()):
        systems: dict[str, list[dict]] = {}
        for system in ("ciclope", "argus"):
            sd = img_dir / system
            runs = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(sd.glob("run-*.json"))] if sd.is_dir() else []
            if runs:
                systems[system] = runs
        if systems:
            out[img_dir.name] = systems
    return out


def _pointwise(image: str, system: str, idx: int, tm: dict, *, force: bool, results_dir: Path) -> dict:
    out = results_dir / image / system / f"judge-{idx}.json"
    if out.exists() and not force:
        return json.loads(out.read_text(encoding="utf-8"))
    res = judge.judge_pointwise(tm, report_id=f"{image}-{system}-{idx}")
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def _pairwise(image: str, tm_c: dict, tm_a: dict, *, force: bool, results_dir: Path) -> dict:
    out = results_dir / image / "judge-pairwise.json"
    if out.exists() and not force:
        return json.loads(out.read_text(encoding="utf-8"))
    # contexto compartilhado = componentes do ARGUS (detector determinístico, mais completos) p/ as
    # duas ordens lerem a MESMA arquitetura. Limitação reference-free; o gold set (5.3) traz GT neutra.
    res = judge.judge_pairwise(tm_c, tm_a, labels=("ciclope", "argus"), context=tm_a)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def _dim_scores(verdict: dict) -> dict[str, int]:
    return {s["dimension"]: s["score"] for s in verdict["verdict"]["scores"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LLM-as-judge sobre os caches do 5.1 (Fase 5).")
    ap.add_argument("--force", action="store_true", help="ignora o cache dos vereditos e re-julga")
    ap.add_argument("--pointwise-only", action="store_true", help="pula o pairwise")
    args = ap.parse_args(argv)

    rd = harness.RESULTS_DIR
    data = load_cached(rd)
    if not data:
        print(f"⚠️  Nenhum relatório cacheado em {rd} — rode o eval/run_comparison.py antes.")
        return 1

    pw_summary: dict[tuple[str, str], dict] = {}
    pairwise_out: dict[str, dict] = {}
    for image, systems in data.items():
        for system, runs in systems.items():
            scores, dims = [], {d: [] for d in judge.DIMENSIONS}
            for i, tm in enumerate(runs):
                try:
                    v = _pointwise(image, system, i, tm, force=args.force, results_dir=rd)
                except Exception as e:  # noqa: BLE001 — uma falha não derruba o lote
                    print(f"  pointwise · {image} · {system} · run {i} → ERRO: {type(e).__name__}: {e}")
                    continue
                scores.append(v["score_0to100"])
                for d, s in _dim_scores(v).items():
                    dims.setdefault(d, []).append(s)
                print(f"  pointwise · {image} · {system} · run {i} → {v['score_0to100']}")
            pw_summary[(image, system)] = {
                "n": len(scores),
                "score": metrics.aggregate(scores),
                "dims": {d: metrics.aggregate(v) for d, v in dims.items()},
            }
        if not args.pointwise_only and {"ciclope", "argus"} <= set(systems):
            try:
                pr = _pairwise(image, systems["ciclope"][0], systems["argus"][0], force=args.force, results_dir=rd)
                pairwise_out[image] = pr
                print(f"  pairwise · {image} → vencedor: {pr['overall_winner']} ({pr['confidence']})")
            except Exception as e:  # noqa: BLE001
                print(f"  pairwise · {image} → ERRO: {type(e).__name__}: {e}")

    # ── Tabelas ──
    lines = ["## Qualidade (LLM-as-judge, Opus 4.8) — pointwise (média±desvio das N execuções)", ""]
    lines.append("| Imagem | Sistema | N | Qualidade (0–100) | cov | spec | action | sev | consist |")
    lines.append("|---|---|--:|--:|--:|--:|--:|--:|--:|")
    def sc(a: dict) -> str:
        return "—" if a["mean"] is None else f"{a['mean']:.1f}±{a['std']:.1f}"

    def dm(a: dict) -> str:
        return "—" if a["mean"] is None else f"{a['mean']:.1f}"

    for (image, system), s in pw_summary.items():
        d = s["dims"]
        lines.append(
            f"| {image} | {system} | {s['n']} | {sc(s['score'])} "
            f"| {dm(d['coverage'])} | {dm(d['specificity'])} | {dm(d['actionability'])} "
            f"| {dm(d['severity_calibration'])} | {dm(d['consistency'])} |"
        )
    if pairwise_out:
        lines += ["", "## Pairwise Cíclope × ARGUS (run-0, dupla ordem)", ""]
        lines.append("| Imagem | Vencedor geral | Confiança | Por dimensão (cov/spec/action/sev/consist) |")
        lines.append("|---|---|---|---|")
        for image, pr in pairwise_out.items():
            pd = pr["per_dimension"]
            per = " · ".join(pd.get(d, "—") for d in judge.DIMENSIONS)
            lines.append(f"| {image} | **{pr['overall_winner']}** | {pr['confidence']} | {per} |")
    table = "\n".join(lines)
    print("\n" + table + "\n")

    (rd / "judge_summary.md").write_text(table + "\n", encoding="utf-8")
    payload = {
        "pointwise": {f"{img}::{sys_}": s for (img, sys_), s in pw_summary.items()},
        "pairwise": pairwise_out,
    }
    (rd / "judge_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ vereditos e resumo em {rd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
