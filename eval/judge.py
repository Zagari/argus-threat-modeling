"""LLM-as-a-judge (Fase 5, Lote 5.2) — avalia a QUALIDADE de relatórios STRIDE.

Implementa `docs/eval-judge-spec.md`: pointwise (nota 0–100) + pairwise (vencedor por dimensão),
**cego** (remove provenance e rótulos "ARGUS"/"Cíclope"), `rationale`+`evidence` ANTES do `score`,
agregação ponderada **em Python** (não no LLM), `temperature=0`. Juiz de família DIFERENTE do
gerador (Gemini): **Claude Opus via Vercel AI Gateway** (anti self-preference).

Config por env (separada do gerador): `JUDGE_MODEL`, `JUDGE_API_KEY` (chave do Vercel AI Gateway —
litellm tem provider nativo `vercel_ai_gateway/` que lê `VERCEL_AI_GATEWAY_API_KEY`; fazemos a ponte),
`JUDGE_TEMPERATURE`. Roda no `.venv-ml` (ou em qualquer venv com litellm).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field, ValidationError

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_PROMPTS = _BACKEND / "app" / "llm" / "prompts"
_env = Environment(loader=FileSystemLoader(_PROMPTS), autoescape=select_autoescape(disabled_extensions=("j2",)))

_DEFAULT_MODEL = "vercel_ai_gateway/anthropic/claude-opus-4.8"

DIMENSIONS = ("coverage", "specificity", "actionability", "severity_calibration", "consistency")
WEIGHTS = {"coverage": 0.25, "specificity": 0.25, "actionability": 0.20, "severity_calibration": 0.15, "consistency": 0.15}

# Âncoras 1/3/5 da rubrica (spec §4). Notas 2 e 4 interpolam.
ANCHORS: dict[str, dict[int, str]] = {
    "coverage": {
        1: "só 1–2 categorias; grandes lacunas frente aos elementos do DFD",
        3: "principais cobertas, mas faltam categorias aplicáveis a alguns elementos",
        5: "todas as categorias STRIDE aplicáveis por elemento cobertas; sem lacunas óbvias",
    },
    "specificity": {
        1: "predominantemente genérica; aplicaria a qualquer sistema",
        3: "mistura equilibrada de específicas e genéricas",
        5: "cada ameaça referencia componentes/fluxos concretos do diagrama; cenários contextualizados",
    },
    "actionability": {
        1: "mitigações ausentes, erradas ou puramente genéricas",
        3: "corretas porém vagas (ex.: 'use criptografia')",
        5: "concretas, implementáveis e mapeadas à ameaça, com referência/controle (ASVS/D3FEND/NIST)",
    },
    "severity_calibration": {
        1: "severidades arbitrárias ou invertidas",
        3: "plausível em geral, com alguns desvios",
        5: "coerentes com exposição/impacto reais (ex.: fluxo externo não autenticado = Alto)",
    },
    "consistency": {
        1: "contradições relevantes (cita componente fora do DFD; IDs contraditórios)",
        3: "pequenas inconsistências",
        5: "sem contradições; IDs, componentes e severidades coerentes em todo o relatório",
    },
}

SYSTEM_POINTWISE = (
    "Você é um avaliador sênior e imparcial de relatórios de modelagem de ameaças STRIDE, com 20+ "
    "anos de experiência. Sua tarefa é PONTUAR a QUALIDADE de um relatório segundo uma rubrica fixa "
    "— não reescrevê-lo. Regras invioláveis: (1) Você NÃO sabe qual ferramenta gerou o relatório; "
    "não especule. (2) Avalie SUBSTÂNCIA, não forma; ignore tamanho/estilo/formatação — relatório "
    "mais longo NÃO é melhor por ser longo. (3) Baseie cada nota APENAS no relatório e no contexto "
    "de arquitetura (e na referência, se houver); não invente fatos. (4) Para cada dimensão, escreva "
    "PRIMEIRO a justificativa e as evidências (citando IDs de ameaça) e SÓ DEPOIS a nota 1–5. "
    "(5) Penalize ameaças genéricas, mitigações vagas e qualquer ameaça que cite componente "
    "inexistente no DFD. (6) Seja calibrado: use toda a escala 1–5. (7) Responda no schema JSON, em português."
)
SYSTEM_PAIRWISE = (
    "Você é um avaliador sênior e imparcial de relatórios STRIDE. Compare DOIS relatórios (A e B) da "
    "MESMA arquitetura e decida, por dimensão, qual é melhor (A, B ou empate). Você NÃO sabe quais "
    "ferramentas os geraram. Avalie SUBSTÂNCIA, não tamanho/estilo. Escreva a justificativa ANTES do "
    "veredito. Responda no schema JSON, em português."
)


# ── Schemas ──────────────────────────────────────────────────────────────────
class DimensionScore(BaseModel):
    dimension: Literal["coverage", "specificity", "actionability", "severity_calibration", "consistency"]
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    score: int = Field(ge=1, le=5)


class JudgeVerdict(BaseModel):
    report_id: str = "report"
    scores: list[DimensionScore]
    flags: list[str] = Field(default_factory=list)
    overall_comment: str = ""


class PairwiseDimension(BaseModel):
    dimension: str
    rationale: str
    winner: Literal["A", "B", "tie"]


class PairwiseVerdict(BaseModel):
    per_dimension: list[PairwiseDimension]
    overall_winner: Literal["A", "B", "tie"]
    confidence: Literal["low", "medium", "high"] = "medium"
    rationale: str = ""


# ── Anonimização (cegueira) ──────────────────────────────────────────────────
_TOOL_RE = re.compile(r"(?i)\b(argus|c[ií]clope)\b")


def _scrub(obj: object) -> object:
    """Remove rótulos de ferramenta de QUALQUER string do objeto (recursivo via JSON)."""
    return json.loads(_TOOL_RE.sub("[sistema]", json.dumps(obj, ensure_ascii=False, default=str)))


def anonymize_report(tm: dict) -> list[dict]:
    """Lista de ameaças sem `provenance` e sem rótulos de ferramenta (juiz cego)."""
    threats = [{k: v for k, v in t.items() if k != "provenance"} for t in tm.get("threats", [])]
    return _scrub(threats)  # type: ignore[return-value]


def _context(tm: dict) -> tuple[str, str]:
    """(components_json, edges_json) da arquitetura — anonimizado."""
    comps = _scrub([
        {k: c.get(k) for k in ("id", "canonical", "element_type", "label") if k in c}
        for c in tm.get("components", [])
    ])
    edges = tm.get("edges") or (tm.get("meta") or {}).get("edges") or []
    return json.dumps(comps, ensure_ascii=False), json.dumps(_scrub(edges), ensure_ascii=False)


# ── Agregação (determinística, fora do LLM — spec §6) ────────────────────────
def weighted_total(scores: list[DimensionScore]) -> dict:
    by = {s.dimension: s.score for s in scores}
    w = sum(by.get(d, 0) * WEIGHTS[d] for d in DIMENSIONS)  # 1..5 (0 se faltar dimensão)
    return {"weighted_1to5": round(w, 3), "score_0to100": round((w - 1) / 4 * 100, 1)}


# ── Chamada ao juiz (config própria; litellm) ────────────────────────────────
def _parse_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t.split("\n", 1)[1] if "\n" in t else t
    i, j = t.find("{"), t.rfind("}")
    if i == -1 or j == -1:
        raise ValueError("nenhum objeto JSON na resposta do juiz")
    return json.loads(t[i : j + 1])


def _llm_text(messages: list[dict], model: str, temperature: float, max_tokens: int) -> str:
    import litellm  # import tardio: o módulo é importável (testes offline) sem litellm carregado

    resp = litellm.completion(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
    return resp["choices"][0]["message"]["content"]


def _complete(system: str, user: str, model_cls: type[BaseModel]) -> BaseModel:
    """Chama o juiz e valida no schema. Sem `response_format` (o gateway→Anthropic rejeita); o prompt
    pede JSON e `_parse_json` extrai. Re-tenta UMA vez devolvendo o JSON inválido p/ correção (robusto
    a aspas não-escapadas / truncamento)."""
    model = os.getenv("JUDGE_MODEL", _DEFAULT_MODEL)
    key = os.getenv("JUDGE_API_KEY")
    if key:  # ponte p/ o provider nativo do litellm (vercel_ai_gateway lê este env)
        os.environ.setdefault("VERCEL_AI_GATEWAY_API_KEY", key)
    temperature = float(os.getenv("JUDGE_TEMPERATURE", "0") or 0)
    max_tokens = int(os.getenv("JUDGE_MAX_TOKENS", "4096"))  # Anthropic exige; alto p/ não truncar o veredito
    schema = json.dumps(model_cls.model_json_schema(), ensure_ascii=False)
    user2 = (
        user + "\n\nResponda ESTRITAMENTE com UM objeto JSON válido e COMPLETO conforme este schema "
        "(escape aspas internas; sem texto fora do JSON):\n" + schema
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user2}]
    text = _llm_text(messages, model, temperature, max_tokens)
    for attempt in range(2):
        try:
            return model_cls.model_validate(_parse_json(text))
        except (ValueError, ValidationError) as e:
            if attempt == 1:
                raise RuntimeError(f"Saída do juiz não validou após retry: {e}") from e
            messages = messages + [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"O JSON acima é inválido ({e}). Reenvie APENAS o JSON válido e completo."},
            ]
            text = _llm_text(messages, model, temperature, max_tokens)
    raise RuntimeError("inalcançável")


def render_pointwise(tm: dict, *, reference: dict | None = None) -> str:
    comps, edges = _context(tm)
    return _env.get_template("judge_pointwise.j2").render(
        components_json=comps,
        edges_json=edges,
        report_json=json.dumps(anonymize_report(tm), ensure_ascii=False, indent=2),
        reference_json=json.dumps(anonymize_report(reference), ensure_ascii=False) if reference else None,
        a=ANCHORS,
    )


def judge_pointwise(tm: dict, *, reference: dict | None = None, report_id: str = "report") -> dict:
    """Avalia UM relatório (0–100). Requer credenciais do juiz (LLM)."""
    verdict = _complete(SYSTEM_POINTWISE, render_pointwise(tm, reference=reference), JudgeVerdict)
    assert isinstance(verdict, JudgeVerdict)
    verdict.report_id = report_id
    return {"verdict": verdict.model_dump(), **weighted_total(verdict.scores)}


def render_pairwise(tm_a: dict, tm_b: dict, *, context: dict | None = None) -> str:
    comps, edges = _context(context or tm_a)
    return _env.get_template("judge_pairwise.j2").render(
        components_json=comps,
        edges_json=edges,
        report_a_json=json.dumps(anonymize_report(tm_a), ensure_ascii=False, indent=2),
        report_b_json=json.dumps(anonymize_report(tm_b), ensure_ascii=False, indent=2),
    )


def judge_pairwise(
    tm1: dict, tm2: dict, *, labels: tuple[str, str] = ("sys1", "sys2"), context: dict | None = None
) -> dict:
    """Compara dois relatórios corrigindo *position bias*: roda nas DUAS ordens (A↔B) e agrega.

    `tm1`/`tm2` são mapeados a `labels`. Em cada dimensão: vence quem ganhou nas duas ordens; se
    divergir, vira `tie` e baixa a confiança. Requer credenciais do juiz (LLM).
    """
    l1, l2 = labels
    v_ab = _complete(SYSTEM_PAIRWISE, render_pairwise(tm1, tm2, context=context), PairwiseVerdict)
    v_ba = _complete(SYSTEM_PAIRWISE, render_pairwise(tm2, tm1, context=context), PairwiseVerdict)
    assert isinstance(v_ab, PairwiseVerdict) and isinstance(v_ba, PairwiseVerdict)

    # mapeia "A"/"B" de cada ordem para o rótulo real (na ordem AB: A=l1; na ordem BA: A=l2)
    def real(order: str, winner: str) -> str:
        if winner == "tie":
            return "tie"
        a_is = l1 if order == "ab" else l2
        b_is = l2 if order == "ab" else l1
        return a_is if winner == "A" else b_is

    by_dim: dict[str, str] = {}
    d_ab = {d.dimension: d.winner for d in v_ab.per_dimension}
    d_ba = {d.dimension: d.winner for d in v_ba.per_dimension}
    for dim in DIMENSIONS:
        w1, w2 = real("ab", d_ab.get(dim, "tie")), real("ba", d_ba.get(dim, "tie"))
        by_dim[dim] = w1 if w1 == w2 else "tie"  # concordância entre ordens; senão empate

    ov1, ov2 = real("ab", v_ab.overall_winner), real("ba", v_ba.overall_winner)
    overall = ov1 if ov1 == ov2 else "tie"
    confidence = "high" if ov1 == ov2 and ov1 != "tie" else ("low" if ov1 != ov2 else "medium")
    return {
        "labels": list(labels),
        "per_dimension": by_dim,
        "overall_winner": overall,
        "confidence": confidence,
        "orders": {"ab": v_ab.model_dump(), "ba": v_ba.model_dump()},
    }
