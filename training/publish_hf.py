"""Publica o detector treinado (`best.pt`) + Model Card no Hugging Face Hub.

Requer login: `huggingface-cli login` (token com escopo write) ou env HF_TOKEN.

Uso:
  python training/publish_hf.py --weights training/runs/argus-detector/weights/best.pt \\
         --repo SEU_USUARIO/argus-detector --metrics training/runs/argus-detector/metrics.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from taxonomy.loader import load_taxonomy  # noqa: E402

MODEL_CARD = """---
license: apache-2.0
library_name: ultralytics
pipeline_tag: object-detection
tags:
  - object-detection
  - yolo11
  - ultralytics
  - threat-modeling
  - architecture-diagrams
  - stride
  - security
---

# ARGUS — Architecture Component Detector (YOLO11)

Supervised object detector from the **ARGUS** project (FIAP IADT, Phase 5 Hackathon).
It locates cloud/software components in **architecture diagram images** and classifies
them into **{nc} cloud-agnostic canonical classes** (AWS, Azure and GCP icons map to the
same class). This is **stage E1** of the ARGUS pipeline; the later stages (topology, DFD,
STRIDE-per-element, Graph-RAG, scoring/report) operate only on the canonical classes, so
only this visual stage is coupled to each cloud's iconography.

## Classes ({nc})
{classes}

## Metrics (synthetic test set)
{metrics}

> These figures are computed on a held-out split of the **synthetic** dataset
> (in-distribution). On real reference diagrams the detector recognizes most components
> correctly but exhibits a **synthetic-to-real gap** (e.g., it may confuse load balancers
> or external web services with the user class, or a key-vault with a database). Closing
> this gap with a real annotated set is planned future work.

## Training data
**Self-labeled synthetic dataset**: official AWS/Azure/GCP architecture icons composited
onto varied backgrounds with arrows, text labels and trust boundaries. Because the icon
positions are known, YOLO labels are emitted automatically (no manual annotation), which
makes the set scalable. Base model: `yolo11s`, `imgsz=1280`.

## Usage
```python
from ultralytics import YOLO

model = YOLO("best.pt")
results = model("diagram.png", conf=0.25, imgsz=1280)
for b in results[0].boxes:
    print(results[0].names[int(b.cls[0])], float(b.conf[0]))
```

## Intended use & limitations
- **Intended use:** automatic, draft component extraction from cloud architecture diagrams,
  as the first stage of an automated STRIDE threat-modeling pipeline.
- **Limitations:** coupled to the appearance of AWS/Azure/GCP icons; generic/whiteboard
  diagrams or other clouds are meant to be covered by ARGUS's OCR (text-label) path, not by
  this detector. Outputs are drafts and should be reviewed by a human.

## Links
- Project & training code: https://github.com/Zagari/argus-threat-modeling
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Publica best.pt no HF Hub.")
    ap.add_argument("--weights", required=True)
    ap.add_argument("--repo", required=True, help="ex.: usuario/argus-detector")
    ap.add_argument("--metrics", default=None, help="metrics.json p/ a Model Card")
    ap.add_argument("--private", action="store_true")
    args = ap.parse_args()

    weights = Path(args.weights)
    if not weights.exists():
        raise SystemExit(f"pesos não encontrados: {weights}")

    try:
        from huggingface_hub import HfApi
    except ImportError:
        raise SystemExit("instale: pip install huggingface_hub") from None

    taxo = load_taxonomy()
    classes = "\n".join(f"- `{c.yolo_name}` ({c.dfd_type})" for c in taxo.classes)
    metrics_txt = "_(treine e informe --metrics)_"
    if args.metrics and Path(args.metrics).exists():
        m = json.loads(Path(args.metrics).read_text())
        metrics_txt = (f"- **mAP@50**: {m.get('map50')}\n- **mAP@50-95**: {m.get('map50_95')}\n"
                       f"- **Precision**: {m.get('precision')}\n- **Recall**: {m.get('recall')}")
    card = MODEL_CARD.format(nc=taxo.nc, classes=classes, metrics=metrics_txt)

    api = HfApi()
    api.create_repo(args.repo, repo_type="model", private=args.private, exist_ok=True)
    api.upload_file(path_or_fileobj=str(weights), path_in_repo="best.pt", repo_id=args.repo)
    readme = weights.parent / "_README_hf.md"
    readme.write_text(card, encoding="utf-8")
    api.upload_file(path_or_fileobj=str(readme), path_in_repo="README.md", repo_id=args.repo)
    print(f"Publicado: https://huggingface.co/{args.repo}")


if __name__ == "__main__":
    main()
