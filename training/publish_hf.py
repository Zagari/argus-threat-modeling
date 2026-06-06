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
tags:
  - object-detection
  - yolo11
  - threat-modeling
  - architecture-diagrams
  - stride
---

# ARGUS — Detector de componentes de arquitetura (YOLO11)

Detector supervisionado do projeto **ARGUS** (Hackathon FIAP IADT Fase 5): localiza
componentes de nuvem em **imagens de diagramas de arquitetura** e os classifica em
**{nc} classes canônicas agnósticas de nuvem** (AWS/Azure mapeados à mesma classe).
É o estágio **E1** do pipeline; E2–E6 (topologia, DFD, STRIDE, Graph-RAG, relatório)
operam só sobre as classes canônicas.

## Classes ({nc})
{classes}

## Métricas (test set)
{metrics}

## Dados de treino
Dataset **sintético auto-rotulado** (ícones oficiais AWS/Azure/GCP compostos em diagramas
com setas/rótulos/fronteiras) + diagramas reais anotados. Os 2 diagramas-exemplo do
enunciado ficam **apenas no split de teste**.

## Uso
```python
from ultralytics import YOLO
model = YOLO("best.pt")
results = model("diagrama.png")
```

## Limitações
Acoplado à aparência dos ícones AWS/Azure; diagramas de outras nuvens/whiteboard são
cobertos pelo caminho por OCR (rótulo-texto) do ARGUS, não por este detector.
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
