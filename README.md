# ARGUS & Cíclope — Modelagem de Ameaças STRIDE a partir de Diagramas de Arquitetura

> Hackathon IADT — Fase 5 (Pós FIAP) · "FIAP Software Security"

Dois sistemas que recebem a **imagem de um diagrama de arquitetura** (AWS/Azure, agnóstico) e produzem um **relatório de modelagem de ameaças STRIDE** com vulnerabilidades e contramedidas:

- **Cíclope** — baseline *LLM-only* (a imagem vai direto a um VLM → relatório). O melhor baseline possível, para comparação justa.
- **ARGUS** — sistema especialista: detector supervisionado (YOLO11) + OCR + topologia/DFD + STRIDE-per-element + Graph-RAG ancorado (Neo4j) + scoring + revisão humana.

Mais uma **interface web** (React + FastAPI) que mostra os resultados parciais de cada estágio e um **estudo comparativo** Cíclope × ARGUS.

## Estado atual

**Fase 0 — em andamento.** Backend FastAPI + Cíclope ponta a ponta + troca de provider de LLM em runtime + shell React.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI · Pydantic v2 · litellm |
| Frontend | React · Vite · TypeScript |
| LLM | Gemini 2.5 (default) · Anthropic · OpenAI (via litellm, troca em runtime) |
| Relatório | Jinja2 → WeasyPrint (PDF) |
| Detecção (Fase 1+) | Ultralytics YOLO11 |
| Conhecimento (Fase 3+) | Neo4j (Graph-RAG) · Chroma (RAG) |

## Como rodar (Fase 0)

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# health: http://localhost:8000/health  ·  docs: http://localhost:8000/docs
```

Configure a chave do LLM em runtime pela aba **Configurações** da UI (ou via `.env` — ver `.env.example`).

### Frontend
```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

### Tudo via Docker
```bash
docker compose up --build
```

## Licença

A definir.
