"""Agregação de métricas do estudo comparativo (Fase 5) — funções **puras** e determinísticas.

Recebe as execuções já medidas (``measure_runs`` do harness) e agrega por ``(imagem, sistema)`` em
**média ± desvio** sobre as N rodadas — é aqui que a variância do VLM vira número. Sem dependências
além da stdlib (testável na CI, sem ML/LLM).
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev

# Métricas escalares agregadas (a chave existe em `metrics` de cada execução, via compare.measure).
_SCALAR = ["n_threats", "groundedness", "id_validity", "ids_valid", "ids_invalid", "n_cves", "latency_s", "cost_usd"]
_DREAD_BANDS = ["Crítico", "Alto", "Médio", "Baixo"]


def aggregate(values: list[float | int | None]) -> dict:
    """Média/desvio populacional/min/max de uma lista, ignorando ``None``. ``std`` é 0 com 1 valor."""
    xs = [float(v) for v in values if v is not None]
    if not xs:
        return {"mean": None, "std": None, "min": None, "max": None, "n": 0}
    return {
        "mean": mean(xs),
        "std": pstdev(xs) if len(xs) > 1 else 0.0,
        "min": min(xs),
        "max": max(xs),
        "n": len(xs),
    }


def summarize(measured: list[dict]) -> dict[tuple[str, str], dict]:
    """Agrupa por ``(imagem, sistema)`` e agrega as N execuções. Chave → resumo agregado."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in measured:
        groups[(r["image"], r["system"])].append(r["metrics"])

    out: dict[tuple[str, str], dict] = {}
    for key, ms in sorted(groups.items()):
        agg: dict = {"n_runs": len(ms)}
        for field in _SCALAR:
            agg[field] = aggregate([m.get(field) for m in ms])
        # DREAD: média da contagem por faixa entre as execuções.
        agg["dread_dist"] = {
            band: aggregate([(m.get("dread_dist") or {}).get(band) for m in ms]) for band in _DREAD_BANDS
        }
        out[key] = agg
    return out


def _ms(agg: dict, *, pct: bool = False, prec: int = 1) -> str:
    """Formata um agregado como ``média±desvio`` (ou ``—`` se vazio)."""
    if agg.get("mean") is None:
        return "—"
    m, s = agg["mean"], agg["std"] or 0.0
    if pct:
        return f"{m * 100:.0f}±{s * 100:.0f}%"
    return f"{m:.{prec}f}±{s:.{prec}f}"


def format_table(summary: dict[tuple[str, str], dict]) -> str:
    """Tabela markdown (média±desvio) por imagem × sistema — a "tabela de variância"."""
    header = (
        "| Imagem | Sistema | N | Ameaças | Groundedness | Validade IDs | CVEs | Latência (s) | Custo (US$) |\n"
        "|---|---|--:|--:|--:|--:|--:|--:|--:|"
    )
    rows = [header]
    for (image, system), a in summary.items():
        rows.append(
            f"| {image} | {system} | {a['n_runs']} "
            f"| {_ms(a['n_threats'])} | {_ms(a['groundedness'], pct=True)} | {_ms(a['id_validity'], pct=True)} "
            f"| {_ms(a['n_cves'])} | {_ms(a['latency_s'])} | {_ms(a['cost_usd'], prec=4)} |"
        )
    return "\n".join(rows)
