# ARGUS & Cíclope — Modelagem de Ameaças STRIDE a partir de Diagramas de Arquitetura

> Hackathon IADT — Fase 5 (Pós FIAP) · "FIAP Software Security"

Dois sistemas que recebem a **imagem de um diagrama de arquitetura** (AWS/Azure/GCP, agnóstico) e produzem um **relatório de modelagem de ameaças STRIDE** com vulnerabilidades e contramedidas:

- **Cíclope** — baseline *LLM-only* (a imagem vai direto a um VLM → relatório). O melhor baseline possível, para comparação justa. **Leve** (não precisa de GPU/ML).
- **ARGUS** — sistema especialista, pipeline de seis estágios: **E1** detector supervisionado (YOLO11) → **E2** OCR + fusão ícone/rótulo + cross-check/topologia (VLM) → **E3** DFD (fronteiras de confiança) → **E4** STRIDE-per-element → **E5** conhecimento ancorado (`CWE→CAPEC→ATT&CK→D3FEND` + `STRIDE→ASVS/NIST`, CVEs reais do NVD; *groundedness* anti-alucinação) → **E6** DREAD + relatório. **Pesado** (precisa de `torch`/OCR).

Mais uma **interface web** (React + FastAPI) que mostra os resultados parciais de cada estágio, a base de conhecimento e o **painel comparativo** Cíclope × ARGUS lado a lado (aba **Comparar**, com a *groundedness* dos dois medida pela mesma régua).

## Estado atual

- **Fase 0** ✅ — backend FastAPI + Cíclope E2E + troca de LLM em runtime + shell React.
- **Fase 1** ✅ — detector YOLO11 (dataset sintético auto-rotulado; mAP@50 0,99 no teste sintético). Modelo: [`zagari/argus-detector`](https://huggingface.co/zagari/argus-detector).
- **Fase 2** ✅ — núcleo ARGUS: **E2** (OCR/fusão/cross-check/topologia), **E3** (DFD), **E4** (STRIDE-per-element) + aba **ARGUS** na UI.
- **Fase 3** ✅ — **conhecimento ancorado** (E5/E6): grafo `CWE→CAPEC→ATT&CK→D3FEND` + `STRIDE→ASVS/NIST` **curado por (classe × STRIDE)** e ranqueado por relevância (fonte de verdade portátil), **CVEs reais** (NVD, cache offline), **groundedness** (validação anti-alucinação) e **DREAD** determinístico. Camadas **opcionais**: **Chroma** (RAG semântico, embeddings locais) e **Neo4j** (Graph-RAG via Cypher + Browser). Ver [Conhecimento ancorado](#conhecimento-ancorado-fase-3--e5e6).
- **Fase 4** 🚧 — **relatório PDF profissional** (estrutura Shostack) ✅ e **painel comparativo** Cíclope × ARGUS ✅; **revisão humana** (aceitar/editar/descartar ameaça) 📋.
- **Fases 5–6** 📋 — estudo comparativo (gold set + LLM-judge), empacotamento.

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI · Pydantic v2 · litellm |
| Frontend | React · Vite · TypeScript |
| LLM | Gemini 2.5 (default) · Anthropic · OpenAI (via litellm, troca em runtime) |
| Detecção (E1) | Ultralytics YOLO11 |
| OCR (E2) | PaddleOCR / EasyOCR (plugável) |
| Relatório | Jinja2 → WeasyPrint (PDF) |
| Conhecimento (E5) | Grafo local (fonte de verdade; CWE/CAPEC/ATT&CK/D3FEND/ASVS/NIST/CVE) · Chroma (RAG semântico, opcional) · Neo4j (Graph-RAG, opcional) |

## Modos de implantação

O backend tem **dois modos**, escolhidos no `docker compose` pela variável `ARGUS_ML`:

| Modo | O que serve | Requisitos | Como subir |
|---|---|---|---|
| **LITE** (padrão) | Só o **Cíclope** (LLM-only) | nenhum extra | `docker compose up --build` |
| **FULL** | Cíclope **+ ARGUS** (E1–E6) | imagem maior (torch CPU); chave de LLM; modelo no HF | `ARGUS_ML=true` (ver abaixo) |

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

## Conhecimento ancorado (Fase 3 — E5/E6)

O ARGUS não "cita de memória": cada ameaça é **ancorada** num grafo de conhecimento curado e **validada** (anti-alucinação). Essa camada tem **três níveis** — o primeiro é sempre ligado; os outros dois são **opcionais** e *degradam graciosamente* (sem eles, o sistema funciona e entrega os mesmos resultados de base).

### 1. Grafo local — sempre ligado, é a fonte de verdade
Um grafo em memória (`LocalKG`), versionado **dentro do pacote** (`backend/app/argus/knowledge/catalog/`), liga — por (classe de componente × categoria STRIDE):

`CWE` (fraquezas) → `CAPEC` (padrões de ataque) → `ATT&CK` (técnicas) → `D3FEND` (contramedidas), mais `STRIDE → ASVS / NIST 800-53` (controles) e **CVEs reais** do NVD (cache offline, **sem** chamadas de rede em runtime).

- **Curadoria por classe (3.9):** o mapa de fraquezas/contramedidas é **curado por (classe × STRIDE)** sobre um piso por propriedade — `database_sql`+Tampering ancora em SQLi (CWE-89), `api_gateway`+Tampering em mass assignment/request smuggling. Cada id é validado contra o catálogo (anti-alucinação na própria curadoria).
- **Ranqueado antes do corte (3.10):** os candidatos das cadeias são ordenados por relevância intrínseca (CAPEC por *Likelihood*+*Severity*+abstração; ASVS por nível L1>L2>L3) antes do teto por salto — os N escolhidos são os mais pertinentes, não os primeiros do catálogo.
- **Groundedness (anti-alucinação):** um validador confere se cada id citado (CWE/CAPEC/ATT&CK/CVE…) **existe** no grafo; ids inventados são descartados. É a mesma "régua" aplicada aos dois sistemas no estudo comparativo (Fase 5).
- **E6 = DREAD** determinístico (defaults por tipo de elemento × STRIDE) para reduzir subjetividade.
- **Explorável:** a aba **Conhecimento** mostra o subgrafo em duas visões — **Camadas** (diagrama por níveis) e **Grafo** (panorama force-directed das 6 categorias STRIDE da classe) —, com nós clicáveis até a fonte oficial.
- **Portátil:** segue na imagem Docker, sem serviço externo. **Nada a configurar.**

### 2. Chroma — RAG semântico (opcional)
**O que é:** um banco **vetorial**. Indexa cada entidade do grafo como um *embedding* (vetor de significado, com modelo **local** multilíngue PT↔EN) e responde "quais entidades se parecem com este texto".

**O que agrega:** *recall por significado*. Além das âncoras determinísticas (mapeamento curado), o E5 levanta candidatos **semânticos** — ex.: uma ameaça descrita em português casa com um CWE em inglês que o mapa fixo não previa. As âncoras que vêm **só** da semântica recebem o selo **≈sem** na UI.

**O que se perde sem ele:** nada de base — cai no **determinístico** (mapeamento curado) e a busca do Explorer vira **substring**. É um *realce de recall*, não um requisito.

**Como ligar** (precisa das deps de ML — modo **FULL**):
```bash
ARGUS_RAG=1     # no .env; no 1º start baixa o modelo e indexa em background (status na aba Início)
# ARGUS_EMBED_MODEL=paraphrase-multilingual-MiniLM-L12-v2   # default; bge-m3 = mais pesado/preciso
```
O índice (Chroma) e o modelo persistem num **volume** → não re-baixam/re-indexam a cada deploy.

### 3. Neo4j — Graph-RAG "de verdade" (opcional)
**O que é:** um banco de **grafo**. Guarda nós **e arestas** como cidadãos de 1ª classe e permite consultas **multi-hop em Cypher** + visualização no **Neo4j Browser**.

**O que agrega:** o **mesmo** grafo, agora navegável/consultável como grafo (ótimo para explicar e gravar o vídeo). Selecionado por `ARGUS_KG_BACKEND=neo4j`, com **fallback automático** ao `LocalKG` se a instância não responder.

**Importante — equivalência comprovada:** o teste `pytest -m neo4j` verifica `LocalKG.subgraph == Neo4jKG.subgraph` (mesmos nós **e** arestas) em todas as categorias STRIDE. Ou seja, **os resultados são idênticos** com ou sem Neo4j — ele é **profundidade/vitrine**, não correção. O `LocalKG` continua a fonte de verdade.

**Como ligar (dev local):**
```bash
docker compose --profile full up -d neo4j          # Neo4j: 7474 = Browser, 7687 = bolt
cd backend && python -m app.argus.knowledge.ingest.mirror_neo4j   # espelha o LocalKG (driver em requirements-ml)
ARGUS_KG_BACKEND=neo4j NEO4J_URI=bolt://localhost:7687 uvicorn app.main:app --reload
# Browser: http://localhost:7474  (neo4j / arguspass)  ·  ex. de Cypher:
#   MATCH p=(s:Stride {name:'Spoofing'})-[:REALIZED_BY]->()-[:EXPLOITED_BY]->()-[:MAPS_TO]->() RETURN p LIMIT 50
```
Reespelhe (`mirror_neo4j`) **quando os catálogos mudarem**; o grafo persiste no volume `neo4j_data`.

> **Em produção, os dois são opt-in.** Por padrão o deploy roda **só o `LocalKG`** (nada a fazer).
> Para ligar no servidor, ver `deploy/.env.prod.example`: o Chroma é `ARGUS_RAG=1`; o Neo4j sobe pelo
> profile `graph` (`docker compose -f docker-compose.prod.yml --profile graph up -d neo4j`, fora do
> deploy padrão) + `ARGUS_KG_BACKEND=neo4j`. Como os resultados são **idênticos**, em prod o ganho do
> Neo4j é apenas a visualização.

## Desenvolvimento local (sem Docker)

```bash
# Backend — LITE (Cíclope)
cd backend && python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Backend — FULL (ARGUS): instale também as deps de ML
pip install -r requirements-ml.txt          # detector/OCR (ultralytics, easyocr) + RAG (chromadb, sentence-transformers) + neo4j
export ARGUS_DETECTOR_HF=zagari/argus-detector GEMINI_API_KEY=sua-chave

# Frontend
cd frontend && npm install && npm run dev    # http://localhost:5173
```

Configure a chave do LLM em runtime pela aba **Configurações** da UI, ou via `.env`
(`.env.example` lista todas as variáveis, incluindo o bloco do pipeline ARGUS).

## Licença

A definir.
