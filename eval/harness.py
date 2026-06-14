"""Harness do estudo comparativo (Fase 5).

Roda Cíclope × ARGUS sobre um conjunto de diagramas, **N execuções cada**, com **cache** em
``eval/results/`` (reruns reproduzíveis e sem re-gasto de LLM). Cada execução é medida com a
**régua única** (`app.compare.measure`) — exatamente os mesmos números do painel "Comparar".

Ciente do ambiente: o **Cíclope** roda em qualquer lugar (só precisa do LLM); o **ARGUS** exige o
detector (deps de ML + pesos) e é **pulado** quando `detect.available()` é falso (ex.: Mac LITE) —
nesse caso, rode o notebook no servidor (com ML). Execução **sequencial** de propósito (chamadas
concorrentes ao VLM disputam o rate-limit e degradam o ARGUS).

Uso típico: ver ``eval/run_comparison.py`` (CLI) e ``eval/run_comparison.ipynb`` (servidor).
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

# Torna o pacote `app` (backend) importável a partir de eval/ — o harness roda no venv do backend
# (LITE no Mac → só Cíclope; completo no servidor → os dois).
_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app import compare  # noqa: E402
from app.argus import detect, orchestrator  # noqa: E402
from app.ciclope import pipeline as ciclope  # noqa: E402
from app.schemas import ThreatModel  # noqa: E402

SYSTEMS = ("ciclope", "argus")
GOLD_DIR = _ROOT / "data" / "gold"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def default_images() -> list[Path]:
    """As 2 Figuras do enunciado (ponto de partida do Lote 5.1, antes do gold set completo)."""
    return sorted(p for p in GOLD_DIR.glob("figura-*") if p.suffix.lower() in _MIME)


def _mime_for(path: Path) -> str:
    return _MIME.get(path.suffix.lower(), "image/jpeg")


def _run_system(system: str, image_bytes: bytes, mime: str) -> ThreatModel:
    if system == "ciclope":
        return ciclope.analyze(image_bytes, mime=mime)
    if system == "argus":
        return orchestrator.run(image_bytes)
    raise ValueError(f"sistema inválido: {system}")


def run_one(
    system: str,
    image_path: Path,
    idx: int,
    *,
    force: bool = False,
    results_dir: Path = RESULTS_DIR,
) -> dict:
    """Roda UMA execução (ou carrega do cache) e devolve ``{system, image, run, tm|error}``."""
    out = results_dir / image_path.stem / system / f"run-{idx}.json"
    rec: dict = {"system": system, "image": image_path.name, "run": idx}
    if out.exists() and not force:
        rec["tm"] = json.loads(out.read_text(encoding="utf-8"))
        rec["cached"] = True
        return rec
    try:
        tm = _run_system(system, image_path.read_bytes(), _mime_for(image_path))
        d = tm.model_dump()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        rec["tm"] = d
        rec["cached"] = False
    except Exception as e:  # noqa: BLE001 — uma falha não derruba a matriz inteira
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc()
    return rec


def run_matrix(
    images: list[Path] | None = None,
    *,
    systems: tuple[str, ...] = SYSTEMS,
    n: int = 3,
    force: bool = False,
    sleep_s: float = 0.0,
    results_dir: Path = RESULTS_DIR,
    log=print,
) -> list[dict]:
    """Roda a matriz (imagens × sistemas × N), **sequencial**, pulando o ARGUS sem detector."""
    imgs = images if images is not None else default_images()
    if not imgs:
        log("⚠️  Nenhuma imagem encontrada (procure em data/gold/figura-* ou passe --images).")
        return []
    argus_ok = detect.available()
    runs: list[dict] = []
    for img in imgs:
        for system in systems:
            if system == "argus" and not argus_ok:
                log(f"⏭️  ARGUS pulado em {img.name}: detector indisponível (ambiente sem ML).")
                continue
            for i in range(n):
                rec = run_one(system, img, i, force=force, results_dir=results_dir)
                tag = "cache" if rec.get("cached") else ("ERRO" if "error" in rec else "novo")
                log(f"  {system:7} · {img.name} · run {i + 1}/{n} [{tag}]"
                    + (f" — {rec['error']}" if "error" in rec else ""))
                runs.append(rec)
                if sleep_s and not rec.get("cached") and "error" not in rec:
                    time.sleep(sleep_s)
    return runs


def measure_runs(runs: list[dict]) -> list[dict]:
    """Mede cada execução com a régua única; descarta as que falharam. Devolve ``{system,image,run,metrics}``."""
    out: list[dict] = []
    for r in runs:
        if "tm" not in r:
            continue
        metrics = compare.measure(ThreatModel.model_validate(r["tm"]))
        out.append({"system": r["system"], "image": r["image"], "run": r["run"], "metrics": metrics})
    return out
