"""Treina o detector YOLO11 do ARGUS na GPU local (RTX A5000) — espelho do notebook.

Lê `train_config.yaml`, treina, valida e escreve `runs/<name>/metrics.json`
(mAP@50, mAP@50-95, P/R médios e por classe). Use `--quick` p/ um smoke de 1 época.

Exemplos:
  python training/train_local.py                       # treino completo (config)
  python training/train_local.py --epochs 1 --quick    # sanidade (1 época, imgsz 640)
  python training/train_local.py --data data/merged/data.yaml --model yolo11m.pt
  python training/train_local.py --yolo-world-baseline  # baseline zero-shot p/ comparar
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "train_config.yaml"


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _resolve_data(data: str) -> str:
    """Resolve o data.yaml relativo à raiz do repo (pai de training/)."""
    p = Path(data)
    if p.is_absolute() or p.exists():
        return str(p)
    repo_root = HERE.parent
    return str(repo_root / data)


def write_metrics(model, val_metrics, out_dir: Path) -> dict:
    box = val_metrics.box
    names = model.names  # {idx: name}
    per_class = {}
    # box.maps é mAP50-95 por classe, na ordem dos índices presentes em val
    try:
        for i, ap in enumerate(box.maps):
            per_class[names.get(i, str(i))] = round(float(ap), 4)
    except Exception:  # noqa: BLE001
        per_class = {}
    metrics = {
        "map50": round(float(box.map50), 4),
        "map50_95": round(float(box.map), 4),
        "precision": round(float(box.mp), 4),
        "recall": round(float(box.mr), 4),
        "per_class_map50_95": per_class,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    return metrics


def run_yolo_world_baseline(cfg: dict, data: str) -> None:
    """Baseline zero-shot (sem treino) p/ evidenciar o ganho do fine-tune."""
    try:
        from ultralytics import YOLOWorld
    except ImportError:
        print("ultralytics não instalado — pule o baseline ou instale requirements-train.txt")
        return
    from taxonomy.loader import load_taxonomy  # noqa: PLC0415
    taxo = load_taxonomy()
    model = YOLOWorld("yolov8s-world.pt")
    model.set_classes([c.yolo_name.replace("_", " ") for c in taxo.classes])
    m = model.val(data=data, imgsz=cfg.get("imgsz", 1280))
    print(f"[YOLO-World zero-shot] mAP@50={float(m.box.map50):.4f} mAP@50-95={float(m.box.map):.4f}")


def main() -> None:
    import sys
    sys.path.insert(0, str(HERE))

    ap = argparse.ArgumentParser(description="Treina o detector YOLO11 do ARGUS.")
    ap.add_argument("--config", default=str(CONFIG_PATH))
    ap.add_argument("--data", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--imgsz", type=int, default=None)
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--device", default=None, help="ex.: 0, 0,1, cpu, mps")
    ap.add_argument("--name", default=None)
    ap.add_argument("--quick", action="store_true", help="smoke: 1 época, imgsz 640, batch pequeno")
    ap.add_argument("--yolo-world-baseline", action="store_true")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    # overrides de CLI
    for key in ("data", "model", "epochs", "imgsz", "batch", "device", "name"):
        v = getattr(args, key)
        if v is not None:
            cfg[key] = v
    if args.quick:
        cfg.update({"epochs": cfg.get("epochs", 1) if args.epochs else 1,
                    "imgsz": args.imgsz or 640, "batch": args.batch or 4,
                    "mosaic": 0.0, "close_mosaic": 0, "name": args.name or "quick"})

    cfg["data"] = _resolve_data(cfg["data"])
    if not Path(cfg["data"]).exists():
        raise SystemExit(f"data.yaml não encontrado: {cfg['data']}\n"
                         f"Gere antes: python training/synthetic/generate_synthetic.py --out data/synthetic")

    try:
        from ultralytics import YOLO
    except ImportError:
        raise SystemExit("ultralytics não instalado. Use o venv de treino:\n"
                         "  python3.12 -m venv training/.venv-train && "
                         "source training/.venv-train/bin/activate && "
                         "pip install -r training/requirements-train.txt") from None

    if args.yolo_world_baseline:
        run_yolo_world_baseline(cfg, cfg["data"])
        return

    train_keys = {"data", "imgsz", "epochs", "batch", "patience", "freeze", "optimizer",
                  "lr0", "cos_lr", "mosaic", "close_mosaic", "hsv_h", "hsv_s", "hsv_v",
                  "degrees", "translate", "scale", "fliplr", "flipud", "project", "name",
                  "seed", "device"}
    train_args = {k: cfg[k] for k in train_keys if k in cfg}

    model = YOLO(cfg["model"])
    results = model.train(**train_args)
    val_metrics = model.val()

    out_dir = Path(cfg["project"]) / cfg.get("name", "argus-detector")
    save_dir = Path(getattr(results, "save_dir", out_dir))
    metrics = write_metrics(model, val_metrics, save_dir)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    best = save_dir / "weights" / "best.pt"
    print(f"\nPesos: {best}\nMétricas: {save_dir / 'metrics.json'}")
    print("Publique no HF Hub: python training/publish_hf.py "
          f"--weights {best} --repo SEU_USUARIO/argus-detector")


if __name__ == "__main__":
    main()
