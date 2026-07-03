"""ARGUS & Cíclope — Hugging Face Space (Gradio) · bring-your-own-key demo.

A public, zero-cost-to-the-owner demo: the visitor picks an LLM provider
(Gemini / Anthropic / OpenAI) and pastes their OWN API key. The key is used
only for that request, is never stored and never logged. It reuses the exact
backend pipeline (same `ThreatModel`, same grounding "ruler"), so the demo
mirrors the real system.

Run locally:  python deploy/hf_space/app.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# ── Locate the backend package (`app`) — works both in the Space layout
#    (./backend/app, so _HERE is the repo root at /app) and in the monorepo
#    layout (../../backend/app, so the root is two levels up). ──
_HERE = Path(__file__).resolve().parent
# Candidate roots, built defensively: in the Space, _HERE == /app has a single
# parent (/), so indexing parents[1] would raise IndexError — only add it if present.
_ROOTS = [_HERE]
if len(_HERE.parents) >= 2:
    _ROOTS.append(_HERE.parents[1])

for _root in _ROOTS:
    _cand = _root / "backend"
    if (_cand / "app" / "config.py").exists():
        sys.path.insert(0, str(_cand))
        break

# Detector (E1) comes from the public HF Hub repo; the label map (E2) from the
# taxonomy YAML if it travels with the repo. Both degrade gracefully if absent.
os.environ.setdefault("ARGUS_DETECTOR_HF", "zagari/argus-detector")
# The YAML lives beside the app in the Space layout (./training/...) and up in the
# monorepo layout (../../training/...). Try both roots.
for _root in _ROOTS:
    _m = _root / "training" / "taxonomy" / "mapeamento.yaml"
    if _m.exists():
        os.environ.setdefault("ARGUS_MAPEAMENTO", str(_m))
        break

import gradio as gr  # noqa: E402

from app import compare  # noqa: E402
from app.argus import detect as detector  # noqa: E402
from app.argus import orchestrator  # noqa: E402
from app.ciclope.pipeline import analyze as ciclope_analyze  # noqa: E402
from app.config import get_config  # noqa: E402
from app.report.render import to_pdf  # noqa: E402

# Provider label -> (internal provider id, hardcoded model id in litellm format)
PROVIDERS: dict[str, tuple[str, str]] = {
    "Google Gemini (gemini-2.5-flash)": ("gemini", "gemini/gemini-2.5-flash"),
    "Anthropic Claude (sonnet-4.5)": ("anthropic", "anthropic/claude-sonnet-4-5"),
    "OpenAI GPT (gpt-4o)": ("openai", "openai/gpt-4o"),
}

SYSTEMS = {
    "Cíclope — LLM-only baseline (fast)": "ciclope",
    "ARGUS — expert pipeline E1–E6 (slower, needs the detector)": "argus",
}

_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _mime_for(path: str) -> str:
    return _MIME.get(Path(path).suffix.lower(), "image/png")


def _threats_rows(tm) -> list[list]:
    rows = []
    for t in tm.threats:
        mit = t.mitigations[0].description if t.mitigations else ""
        rows.append([
            t.id,
            t.component_id,
            str(t.stride_category),
            t.title,
            f"{t.impact}/{t.likelihood} ({t.risk_score})",
            t.dread_band or "",
            ", ".join(t.cwe_ids[:3]),
            (mit[:160] + "…") if len(mit) > 160 else mit,
        ])
    return rows


def _components_rows(tm) -> list[list]:
    return [[c.id, c.canonical, c.element_type, c.label or ""] for c in tm.components]


def run(image_path, provider_label, api_key, system_label):
    """Blind, per-request run. Returns (summary_md, components, threats, pdf_path)."""
    if not image_path:
        return "⚠️ Please upload an architecture diagram first.", [], [], None
    if not api_key or not api_key.strip():
        return "⚠️ Please paste your API key for the selected provider.", [], [], None

    provider, model = PROVIDERS[provider_label]
    system = SYSTEMS[system_label]

    # Point the shared runtime config at the visitor's provider + key, for THIS run.
    # The key lives only in memory (never logged, never returned) — see app/config.py.
    get_config().update(provider=provider, model=model, api_key=api_key.strip(), mock=False)

    if system == "argus" and not detector.available():
        return ("⚠️ ARGUS needs the object detector (E1), which isn't available here. "
                "Try **Cíclope** instead, or run ARGUS locally in FULL mode."), [], [], None

    try:
        img = Path(image_path).read_bytes()
        if system == "argus":
            tm = orchestrator.run(img)
        else:
            tm = ciclope_analyze(img, mime=_mime_for(image_path))
    except Exception as e:  # noqa: BLE001 — surface a friendly message to the user
        name = type(e).__name__
        msg = str(e)
        hint = ""
        if "rate" in msg.lower() or "limit" in msg.lower():
            hint = " (the provider is rate-limiting — wait a few seconds and retry)"
        elif "key" in msg.lower() or "auth" in msg.lower() or "401" in msg:
            hint = " (check that the API key matches the selected provider)"
        return f"❌ Analysis failed — {name}: {msg[:200]}{hint}", [], [], None

    m = compare.measure(tm)  # same grounding ruler applied to both systems
    ground = m.get("groundedness")
    meta = tm.meta or {}
    cost = (meta.get("usage") or {}).get("cost_usd")
    n_cves = meta.get("n_cves")

    summary = [
        f"### {system_label.split('—')[0].strip()} · {provider_label}",
        f"- **Threats found:** {len(tm.threats)}",
        f"- **Groundedness (real CWE/CAPEC/CVE anchors):** {ground*100:.0f}%" if ground is not None else "",
        f"- **Real CVEs cited:** {n_cves}" if n_cves is not None else "",
        f"- **Components detected:** {len(tm.components)}",
        f"- **Estimated cost:** US$ {cost:.4f}" if cost is not None else "",
        "",
        "_Your API key was used only for this request and was not stored._",
    ]
    summary_md = "\n".join(s for s in summary if s != "")

    # PDF report
    pdf_path = None
    try:
        pdf_bytes = to_pdf(tm)
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        f.write(pdf_bytes)
        f.close()
        pdf_path = f.name
    except Exception:  # noqa: BLE001 — report is a bonus; don't fail the run over it
        pdf_path = None

    return summary_md, _components_rows(tm), _threats_rows(tm), pdf_path


DESCRIPTION = """
# 🛡️ ARGUS & Cíclope — STRIDE threat modeling from an architecture diagram

Upload an architecture diagram (AWS / Azure / GCP) and get a **STRIDE threat model** with
vulnerabilities and countermeasures. Two systems share the same output contract:

- **Cíclope** — an LLM-only baseline (the image goes straight to a vision model).
- **ARGUS** — a six-stage expert pipeline (supervised detector → OCR/topology → DFD →
  STRIDE-per-element → grounded knowledge `CWE→CAPEC→ATT&CK→D3FEND` + real CVEs → DREAD).

> **Bring your own key.** Pick a provider and paste your own API key — it is used **only for
> this request**, is **never stored** and **never logged**. Nothing is charged to the demo owner.
> On this free CPU Space, **ARGUS is slow** (detector + OCR + several model calls); try
> **Cíclope** first for a quick result.
"""


def build() -> gr.Blocks:
    with gr.Blocks(title="ARGUS & Cíclope — STRIDE threat modeling") as demo:
        gr.Markdown(DESCRIPTION)
        with gr.Row():
            with gr.Column(scale=1):
                image = gr.Image(type="filepath", label="Architecture diagram")
                provider = gr.Dropdown(list(PROVIDERS), value=list(PROVIDERS)[0], label="LLM provider")
                api_key = gr.Textbox(label="Your API key", type="password",
                                     placeholder="Used only for this request — never stored")
                system = gr.Dropdown(list(SYSTEMS), value=list(SYSTEMS)[0], label="System")
                btn = gr.Button("Analyze", variant="primary")
            with gr.Column(scale=2):
                summary = gr.Markdown(label="Summary")
                with gr.Tab("Threats (STRIDE)"):
                    threats = gr.Dataframe(
                        headers=["ID", "Component", "STRIDE", "Title", "Impact/Likelihood (risk)",
                                 "DREAD", "CWE", "Top mitigation"],
                        wrap=True, label="Threats")
                with gr.Tab("Components (DFD)"):
                    components = gr.Dataframe(
                        headers=["ID", "Canonical class", "DFD type", "Label"], wrap=True, label="Components")
                pdf = gr.File(label="Full STRIDE report (PDF)")
        btn.click(run, inputs=[image, provider, api_key, system],
                  outputs=[summary, components, threats, pdf], concurrency_limit=1)
    return demo


if __name__ == "__main__":
    build().queue().launch()
