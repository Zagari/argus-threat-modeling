# `eval/` — Estudo comparativo Cíclope × ARGUS (Fase 5)

Harness que roda os dois sistemas **N vezes** sobre um conjunto de diagramas, com **cache**, e
agrega as métricas em **média ± desvio** (a variância do VLM vira número). Mede com a **régua
única** (`app.compare.measure`) — os mesmos números do painel "Comparar".

## Pré-requisitos
Roda no **venv do backend** (importa `app`). No **Mac** esse venv costuma ser **LITE** (sem ML) →
o **ARGUS é pulado** e só o **Cíclope** roda. No **servidor** (com ML) rodam os **dois**.
Precisa da chave do LLM gerador no `.env` (ex.: `GEMINI_API_KEY`).

## Rodar no Mac (CLI)
```bash
cd argus
backend/.venv/bin/python eval/run_comparison.py            # 2 Figuras, N=3
backend/.venv/bin/python eval/run_comparison.py --systems ciclope --n 3
backend/.venv/bin/python eval/run_comparison.py --images "data/gold/figura-*.jpg" --force
```

## Rodar no servidor (notebook, inclui ARGUS)
Abra `eval/run_comparison.ipynb` com o **kernel do venv do backend** (com ML) e execute as células.

## Saídas
- `eval/results/<imagem>/<sistema>/run-*.json` — cada `ThreatModel` (cache; reruns não re-gastam LLM).
- `eval/results/summary.{md,json}` — tabela agregada (média±desvio) por imagem × sistema.

## Lotes
- **5.1 (este):** harness + métricas objetivas (groundedness, validade de IDs, ameaças, CVEs, custo, latência) + variância.
- **5.2:** LLM-as-judge (Claude Opus via Vercel AI Gateway), pointwise + pairwise, cego.
- **5.3:** gold set (18, híbrido) + recall/precisão vs gold + mAP/topologia.
- **5.4:** execução final + capítulo comparativo (H1/H2/H3).
