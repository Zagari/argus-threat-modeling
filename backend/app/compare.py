"""Comparação Cíclope × ARGUS (Fase 4, frente 3).

Mede a groundedness dos DOIS sistemas com a MESMA régua (`knowledge/validate.py`) e faz o
diff das ameaças por assinatura `(classe canônica × categoria STRIDE)`. O ARGUS já chega
validado (E5); o Cíclope é medido aqui (validador agnóstico, `drop_invalid=False` — só mede a
alucinação do baseline, não altera a saída). Não roda os pipelines: recebe os dois `ThreatModel`
já prontos (o frontend dispara as duas análises em paralelo via SSE).
"""

from __future__ import annotations

from app.argus.knowledge import validate
from app.argus.knowledge.store import get_store
from app.schemas import ThreatModel


def _signatures(tm: ThreatModel) -> set[tuple[str, str]]:
    """Assinaturas (classe canônica do componente, STRIDE) das ameaças do modelo."""
    canon = {c.id: c.canonical for c in tm.components}
    return {(canon.get(t.component_id, t.component_id), str(t.stride_category)) for t in tm.threats}


def _summary(tm: ThreatModel) -> dict:
    m = tm.meta
    usage = m.get("usage") or {}
    return {
        "system": m.get("system"),
        "system_name": tm.system_name,
        "n_components": len(tm.components),
        "n_threats": len(tm.threats),
        "groundedness": m.get("groundedness"),
        "id_validity": m.get("id_validity"),
        "ids_valid": m.get("ids_valid"),
        "ids_invalid": m.get("ids_invalid"),
        "dread_dist": m.get("dread_dist"),
        "n_cves": m.get("n_cves", 0),
        "latency_s": m.get("latency_s"),
        "cost_usd": usage.get("cost_usd"),
    }


def _fmt(sigs: set[tuple[str, str]]) -> list[dict]:
    return [{"canonical": c, "stride": s} for c, s in sorted(sigs)]


def diff(ciclope: ThreatModel, argus: ThreatModel) -> dict:
    """Resumo por sistema (com groundedness comparável) + diff por (classe × STRIDE)."""
    store = get_store()
    # Régua única: o Cíclope não valida → medir aqui (sem alterar a saída). ARGUS já vem do E5.
    for tm in (ciclope, argus):
        if "groundedness" not in tm.meta:
            validate.validate_model(tm, store, drop_invalid=False)

    sc, sa = _signatures(ciclope), _signatures(argus)
    return {
        "ciclope": _summary(ciclope),
        "argus": _summary(argus),
        "diff": {
            "common": _fmt(sc & sa),
            "only_ciclope": _fmt(sc - sa),
            "only_argus": _fmt(sa - sc),
            "n_common": len(sc & sa),
            "n_only_ciclope": len(sc - sa),
            "n_only_argus": len(sa - sc),
        },
    }
