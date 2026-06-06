"""Testes de sanidade do dataset sintético (rodam offline, sem ultralytics).

Cobrem os critérios automatizados da Fase 1:
  - o gerador produz imagens + labels YOLO válidos;
  - `data.yaml` é coerente (nc == nº de nomes) e os splits não vazam entre si.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from synthetic.generate_synthetic import write_dataset
from taxonomy.loader import load_taxonomy, match_icon_filename, match_label


def _args(out: Path, n: int = 24) -> argparse.Namespace:
    return argparse.Namespace(
        n=n, out=str(out), seed=7, imgsz=640, min_icons=4, max_icons=10,
        train=0.7, val=0.15, icons_dir=None, mapeamento=None, edges=True,
    )


def test_taxonomy_loads_and_is_consistent() -> None:
    t = load_taxonomy()
    assert t.nc >= 20
    # nomes YOLO únicos e seguros (sem barra/espaço)
    names = t.names
    assert len(names) == len(set(names))
    for n in names:
        assert " " not in n and "/" not in n
    # trust_boundary é TrustBoundary; api_gateway tem os 6 STRIDE
    assert t.by_name("trust_boundary").dfd_type == "TrustBoundary"
    assert len(t.by_name("api_gateway").stride) == 6


def test_icon_and_label_matching() -> None:
    assert match_icon_filename("Arch_Amazon-API-Gateway_48.svg", "aws") == "api_gateway"
    assert match_icon_filename("10042-icon-service-API-Management-Services.svg", "azure") == "api_gateway"
    assert match_icon_filename("Arch_Amazon-Simple-Storage-Service_48.svg", "aws") == "object_storage"
    assert match_label("API Gateway", None) == "api_gateway"
    assert match_label("Postgres DB", None) == "database_sql"
    assert match_icon_filename("totally-unknown-thing.svg", "aws") is None


def test_gcp_icon_matching() -> None:
    assert match_icon_filename("cloud-storage.svg", "gcp") == "object_storage"
    assert match_icon_filename("kubernetes-engine.svg", "gcp") == "compute"
    assert match_icon_filename("cloud-sql.svg", "gcp") == "database_sql"
    assert match_icon_filename("pubsub.svg", "gcp") == "message_queue"
    assert match_icon_filename("cloud-functions.svg", "gcp") == "serverless_fn"
    # toda classe com ícone AWS/Azure deveria ter cobertura GCP ou estar consciente disso
    t = load_taxonomy()
    assert t.by_name("compute").gcp  # campo gcp carregado do YAML


def test_generate_produces_valid_yolo_labels(tmp_path: Path) -> None:
    meta = write_dataset(_args(tmp_path))
    t = load_taxonomy()

    imgs = list((tmp_path / "images").rglob("*.png"))
    lbls = list((tmp_path / "labels").rglob("*.txt"))
    assert len(imgs) == 24
    assert len(lbls) == 24

    for lbl in lbls:
        for line in lbl.read_text().splitlines():
            if not line.strip():
                continue
            parts = line.split()
            assert len(parts) == 5
            ci = int(parts[0])
            cx, cy, w, h = (float(x) for x in parts[1:])
            assert 0 <= ci < t.nc
            for v in (cx, cy, w, h):
                assert 0.0 <= v <= 1.0
            assert w > 0 and h > 0

    assert meta["nc"] == t.nc
    assert sum(meta["splits"].values()) == 24


def test_data_yaml_is_coherent(tmp_path: Path) -> None:
    write_dataset(_args(tmp_path))
    data = yaml.safe_load((tmp_path / "data.yaml").read_text())
    assert data["nc"] == len(data["names"])
    assert set(data["names"].values()) == set(load_taxonomy().names)
    for split in ("train", "val", "test"):
        assert (tmp_path / data[split]).is_dir()


def test_no_split_leakage(tmp_path: Path) -> None:
    write_dataset(_args(tmp_path, n=40))
    stems: dict[str, set[str]] = {}
    for split in ("train", "val", "test"):
        stems[split] = {p.stem for p in (tmp_path / "images" / split).glob("*.png")}
    assert stems["train"] and stems["val"] and stems["test"]  # todos não-vazios
    assert not (stems["train"] & stems["val"])
    assert not (stems["train"] & stems["test"])
    assert not (stems["val"] & stems["test"])


def test_every_image_has_one_label(tmp_path: Path) -> None:
    write_dataset(_args(tmp_path))
    for img in (tmp_path / "images").rglob("*.png"):
        split = img.parent.name
        lbl = tmp_path / "labels" / split / f"{img.stem}.txt"
        assert lbl.is_file(), f"label ausente p/ {img}"
        assert lbl.read_text().strip(), f"label vazio p/ {img}"
