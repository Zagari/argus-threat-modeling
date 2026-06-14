# `eval/` — Estudo comparativo Cíclope × ARGUS (Fase 5)

Harness que roda os dois sistemas **N vezes** sobre um conjunto de diagramas, com **cache**, e
agrega as métricas em **média ± desvio** (a variância do VLM vira número). Mede com a **régua
única** (`app.compare.measure`) — os mesmos números do painel "Comparar".

## Pré-requisitos
Roda no venv do backend (importa `app`). Dois caminhos:
- **`.venv-ml` (Python 3.13, com ML)** — **Cíclope + ARGUS** (torch/ultralytics/easyocr + detector E1).
- **`backend/.venv` (Python 3.14, LITE)** — só **Cíclope**; o ARGUS é **pulado** (sem ultralytics).

Precisa da chave do LLM gerador no `.env` (`GEMINI_API_KEY`) e, p/ o ARGUS, do **detector** no `.env`:
`ARGUS_DETECTOR_HF=zagari/argus-detector` + `ARGUS_DETECTOR_FILE=best.pt` (repo **público**, sem token HF;
os pesos são baixados na 1ª detecção). RAG semântico (E5 híbrido) é **opcional**:
`.venv-ml/bin/pip install chromadb sentence-transformers` + `ARGUS_RAG=1` (sem isso, cai no determinístico).

## Rodar no Mac (CLI)
```bash
cd argus
# Cíclope + ARGUS (venv de ML, Python 3.13):
.venv-ml/bin/python eval/run_comparison.py                 # 2 Figuras, N=3, os dois sistemas
.venv-ml/bin/python eval/run_comparison.py --images "data/gold/figura-*.jpg" --force
# Só Cíclope (venv LITE 3.14), se não quiser carregar o ML:
backend/.venv/bin/python eval/run_comparison.py --systems ciclope --n 3
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
