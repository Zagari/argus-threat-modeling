# ARGUS & Cíclope — Modelagem de Ameaças STRIDE a partir de Diagramas de Arquitetura

> Hackathon IADT — Fase 5 (Pós FIAP) · "FIAP Software Security"

Dois sistemas que recebem a **imagem de um diagrama de arquitetura** (AWS/Azure/GCP, agnóstico) e produzem um **relatório de modelagem de ameaças STRIDE** com vulnerabilidades e contramedidas:

- **Cíclope** — baseline *LLM-only* (a imagem vai direto a um VLM → relatório). O melhor baseline possível, para comparação justa. **Leve** (não precisa de GPU/ML).
- **ARGUS** — sistema especialista, pipeline de seis estágios: **E1** detector supervisionado (YOLO11) → **E2** OCR + fusão ícone/rótulo + cross-check/topologia (VLM) → **E3** DFD (fronteiras de confiança) → **E4** STRIDE-per-element → E5 Graph-RAG ancorado (CWE/CAPEC/CVE) → E6 scoring + relatório. **Pesado** (precisa de `torch`/OCR).

Mais uma **interface web** (React + FastAPI) que mostra os resultados parciais de cada estágio e o **estudo comparativo** Cíclope × ARGUS.

## Estado atual

- **Fase 0** ✅ — backend FastAPI + Cíclope E2E + troca de LLM em runtime + shell React.
- **Fase 1** ✅ — detector YOLO11 (dataset sintético auto-rotulado; mAP@50 0,99 no teste sintético). Modelo: [`zagari/argus-detector`](https://huggingface.co/zagari/argus-detector).
- **Fase 2** ✅ — núcleo ARGUS: **E2** (OCR/fusão/cross-check/topologia), **E3** (DFD), **E4** (STRIDE-per-element) + aba "Pipeline ARGUS" na UI.
- **Fases 3–6** 📋 — Graph-RAG (E5), DREAD, estudo comparativo, empacotamento.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI · Pydantic v2 · litellm |
| Frontend | React · Vite · TypeScript |
| LLM | Gemini 2.5 (default) · Anthropic · OpenAI (via litellm, troca em runtime) |
| Detecção (E1) | Ultralytics YOLO11 |
| OCR (E2) | PaddleOCR / EasyOCR (plugável) |
| Relatório | Jinja2 → WeasyPrint (PDF) |
| Conhecimento (E5) | Neo4j (Graph-RAG) · Chroma (RAG) |

## Modos de implantação

O backend tem **dois modos**, escolhidos no `docker compose` pela variável `ARGUS_ML`:

| Modo | O que serve | Requisitos | Como subir |
|---|---|---|---|
| **LITE** (padrão) | Só o **Cíclope** (LLM-only) | nenhum extra | `docker compose up --build` |
| **FULL** | Cíclope **+ ARGUS** (E1–E4) | imagem maior (torch CPU); chave de LLM; modelo no HF | `ARGUS_ML=true` (ver abaixo) |

### LITE (rápido, sem GPU) — só o baseline
```bash
GEMINI_API_KEY=sua-chave docker compose up --build
# UI: http://localhost:8080   ·   backend: http://localhost:8000
```

### FULL (ARGUS completo) — detector + OCR + pipeline
```bash
ARGUS_ML=true \
GEMINI_API_KEY=sua-chave \
ARGUS_DETECTOR_HF=zagari/argus-detector \
docker compose up --build
```
A imagem FULL inclui `torch` (CPU), `ultralytics` e o OCR. Roda em **qualquer máquina** —
a latência do ARGUS (~1–2 min) é dominada pelas chamadas ao VLM, não pelo detector, então
**GPU é opcional**. As chaves e variáveis ficam no shell ou num `.env` (ver `.env.example`).

> **Produção (CI/CD):** o pipeline de CI builda a imagem do backend em modo **FULL**
> (`INSTALL_ML=true`), então o deploy publicado roda o **ARGUS completo**. No servidor, o
> `.env` precisa de `GEMINI_API_KEY`, `ARGUS_DETECTOR_HF=zagari/argus-detector` e
> `ARGUS_LLM_MOCK=0` (ver `deploy/.env.prod.example`). O modo LITE continua disponível para
> quem clonar e buildar localmente sem `ARGUS_ML`.
>
> ⚠️ **Latência atrás de Cloudflare:** a análise do ARGUS leva ~1–2 min (3 chamadas ao VLM),
> próximo do teto ~100s do Cloudflare *free* — pode haver 504 em execuções mais lentas. O
> Cíclope (~30s) não tem esse risco. Mitigação futura: unir as chamadas VLM / análise assíncrona.

## Desenvolvimento local (sem Docker)

```bash
# Backend — LITE (Cíclope)
cd backend && python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Backend — FULL (ARGUS): instale também as deps de ML
pip install -r requirements-ml.txt          # ultralytics, easyocr, huggingface_hub
export ARGUS_DETECTOR_HF=zagari/argus-detector GEMINI_API_KEY=sua-chave

# Frontend
cd frontend && npm install && npm run dev    # http://localhost:5173
```

Configure a chave do LLM em runtime pela aba **Configurações** da UI, ou via `.env`
(`.env.example` lista todas as variáveis, incluindo o bloco do pipeline ARGUS).

## Licença

A definir.
