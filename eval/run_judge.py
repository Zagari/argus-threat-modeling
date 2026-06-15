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
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402  (RESULTS_DIR + path do backend/.env via app.config)
import judge  # noqa: E402
import metrics  # noqa: E402

# garante o carregamento do .env (JUDGE_*) — harness já põe backend no path
import app.config  # noqa: E402,F401

_GOLD = Path(__file__).resolve().parent / "gold"  # GTs neutras revisadas (contexto justo p/ o pairwise)


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


def _modal(dist: dict) -> str:
    return max(dist.items(), key=lambda kv: kv[1])[0] if dist else "—"


def _pairwise(image: str, tm_c: dict, tm_a: dict, *, n: int, force: bool, results_dir: Path) -> dict:
    """Roda o pairwise **N vezes** e agrega a DISTRIBUIÇÃO de vencedores (o juiz é não-determinístico
    mesmo a temp=0 → um único veredito é frágil em casos borderline)."""
    out = results_dir / image / "judge-pairwise.json"
    if out.exists() and not force:
        return json.loads(out.read_text(encoding="utf-8"))
    gt = _GOLD / f"{image}.gt.json"
    context = json.loads(gt.read_text(encoding="utf-8")) if gt.exists() else None  # GT neutra → contexto justo
    runs = [judge.judge_pairwise(tm_c, tm_a, labels=("ciclope", "argus"), context=context) for _ in range(n)]

    overall = Counter(r["overall_winner"] for r in runs)
    res = {
        "n": n,
        "context": "gt_neutra" if context is not None else "reference_free",
        "overall_dist": dict(overall),
        "modal_winner": _modal(dict(overall)),
        "per_dim_dist": {d: dict(Counter(r["per_dimension"].get(d, "tie") for r in runs)) for d in judge.DIMENSIONS},
        "confounded_runs": sum(1 for r in runs if r.get("confounded")),
        "runs": runs,
    }
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def _dim_scores(verdict: dict) -> dict[str, int]:
    return {s["dimension"]: s["score"] for s in verdict["verdict"]["scores"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LLM-as-judge sobre os caches do 5.1 (Fase 5).")
    ap.add_argument("--force", action="store_true", help="ignora o cache dos vereditos e re-julga")
    ap.add_argument("--pointwise-only", action="store_true", help="pula o pairwise")
    ap.add_argument("--judge-n", type=int, default=3, help="execuções do juiz por pairwise (distribuição) [3]")
    ap.add_argument("--only", help="julga só diagramas cujo nome contém um destes (csv) — economiza juiz")
    args = ap.parse_args(argv)

    rd = harness.RESULTS_DIR
    data = load_cached(rd)
    if args.only:
        subs = [s.strip() for s in args.only.split(",") if s.strip()]
        data = {img: syss for img, syss in data.items() if any(s in img for s in subs)}
    if not data:
        print(f"⚠️  Nenhum relatório cacheado em {rd} (ou nenhum casou --only) — rode o eval/run_comparison.py antes.")
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
                pr = _pairwise(image, systems["ciclope"][0], systems["argus"][0],
                               n=args.judge_n, force=args.force, results_dir=rd)
                pairwise_out[image] = pr
                print(f"  pairwise · {image} (N={pr['n']}) → {pr['overall_dist']} | modal: {pr['modal_winner']}")
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
        lines += ["", "## Pairwise Cíclope × ARGUS (N execuções do juiz — distribuição de vencedores)", ""]
        lines.append("| Imagem | Contexto | N | Distribuição (overall) | Modal | Por dimensão (modal) |")
        lines.append("|---|---|--:|---|---|---|")
        for image, pr in pairwise_out.items():
            dist = " / ".join(f"{k}:{v}" for k, v in sorted(pr["overall_dist"].items()))
            perdim = " · ".join(f"{d[:4]}:{_modal(pr['per_dim_dist'][d])}" for d in judge.DIMENSIONS)
            ctx = "GT neutra" if pr.get("context") == "gt_neutra" else "ref-free"
            lines.append(f"| {image} | {ctx} | {pr['n']} | {dist} | **{pr['modal_winner']}** | {perdim} |")
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
