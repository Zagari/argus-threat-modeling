---
title: ARGUS & Cíclope — STRIDE Threat Modeling
emoji: 🛡️
colorFrom: indigo
colorTo: gray
sdk: gradio
sdk_version: 5.9.1
app_file: app.py
pinned: false
license: mit
short_description: STRIDE threat models from an architecture diagram (bring your own key)
---

# 🛡️ ARGUS & Cíclope — STRIDE Threat Modeling from Architecture Diagrams

Upload an architecture diagram (AWS / Azure / GCP) and get a **STRIDE threat model** — threats,
vulnerabilities and countermeasures. Two systems share the same output:

- **Cíclope** — an LLM-only baseline: the image goes straight to a vision model.
- **ARGUS** — a six-stage expert pipeline: supervised detector (YOLO11) → OCR + topology → DFD →
  STRIDE-per-element → grounded knowledge (`CWE → CAPEC → ATT&CK → D3FEND`, `STRIDE → ASVS/NIST`,
  real CVEs from the NVD) → DREAD scoring.

This is the companion demo for the **FIAP IADT — Phase 5 ("FIAP Software Security")** project.

## 🔑 Bring your own key (no cost to the demo owner)

Pick an **LLM provider** and paste your **own API key**:

| Provider | Model used |
|---|---|
| Google Gemini | `gemini-2.5-flash` |
| Anthropic Claude | `claude-sonnet-4-5` |
| OpenAI GPT | `gpt-4o` |

Your key is used **only for that single request**, is **never stored** and **never logged**
(see `app/config.py`: the key is kept in memory and is excluded from `GET /settings` and logs).
Requests are processed **one at a time** so keys never mix between visitors.

> ⚠️ On the free CPU Space, **ARGUS is slow** (it downloads and runs the detector, does OCR and
> several model calls). Try **Cíclope** first for a quick result. The object detector (E1) runs
> **locally** and is free — only the LLM calls use your key.

## 🖥️ Run locally

```bash
python app.py            # from the Space repo root
# or, from the monorepo:
python deploy/hf_space/app.py
```

## 🚀 How to publish this Space (step by step)

1. **Create a Space:** go to <https://huggingface.co/new-space>, choose **SDK = Gradio**, CPU basic.
2. **Add the files** to the Space repo:
   - `app.py` and `requirements.txt` (this folder), and this `README.md`.
   - The **backend package**: copy `backend/app/` into the Space as `backend/app/`
     (the pipeline code, knowledge catalogs included). `app.py` finds it automatically.
   - The **taxonomy** (improves E2 label matching): copy
     `training/taxonomy/mapeamento.yaml` to the same relative path, or set the
     `ARGUS_MAPEAMENTO` variable to its location.
3. **Detector:** nothing to do — it is pulled anonymously from the public Hub repo
   `zagari/argus-detector` (override with the `ARGUS_DETECTOR_HF` variable if needed).
4. **No secrets required:** keys are provided by visitors at runtime (bring-your-own-key).
5. **Push** and wait for the build. First ARGUS run also downloads the detector weights (one-off).
6. *(Optional)* embed a short demo video in this `README.md`.

## 📦 What runs where

- **Local / embedded (no key):** detector (YOLO11), OCR, and the portable knowledge graph (LocalKG).
- **External (your key):** the LLM/vision calls (Cíclope, and ARGUS stages E2/E4/E5).
- **Not on the free Space:** Neo4j (Graph-RAG) and Chroma (semantic RAG) — optional extras used in
  the full local/Docker deployment; the Space uses LocalKG, which returns the same base results.

## 🔗 Links

- **Model (detector):** <https://huggingface.co/zagari/argus-detector>
- **Source code:** <https://github.com/Zagari/argus-threat-modeling>
