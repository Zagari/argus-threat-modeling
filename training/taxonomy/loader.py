"""Carrega `mapeamento.yaml` e expõe a taxonomia canônica para todo o `training/`.

Única dependência: PyYAML. É o ponto único de verdade do vocabulário de classes —
o índice YOLO de cada classe é a sua posição na ordem do YAML. Use sempre
`load_taxonomy()` (cacheado) em vez de reabrir o arquivo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

MAPEAMENTO_PATH = Path(__file__).resolve().parent / "mapeamento.yaml"

# tipos DFD válidos (espelha backend/app/schemas.py ElementType)
VALID_DFD_TYPES = {"Process", "DataStore", "ExternalEntity", "DataFlow", "TrustBoundary"}
VALID_STRIDE = {
    "Spoofing",
    "Tampering",
    "Repudiation",
    "Information Disclosure",
    "Denial of Service",
    "Elevation of Privilege",
}


@dataclass(frozen=True)
class CanonicalClass:
    index: int
    name: str                      # chave canônica, ex.: "api_gateway"
    dfd_type: str
    stride: list[str]
    aws: list[str] = field(default_factory=list)
    azure: list[str] = field(default_factory=list)
    gcp: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    cpe_hints: list[str] = field(default_factory=list)

    @property
    def yolo_name(self) -> str:
        """Nome seguro p/ data.yaml e nomes de arquivo (sem barras/espaços)."""
        return re.sub(r"[^0-9a-zA-Z_]+", "_", self.name)


@dataclass(frozen=True)
class Taxonomy:
    classes: list[CanonicalClass]

    @property
    def names(self) -> list[str]:
        return [c.yolo_name for c in self.classes]

    @property
    def nc(self) -> int:
        return len(self.classes)

    def by_name(self, name: str) -> CanonicalClass:
        for c in self.classes:
            if c.name == name or c.yolo_name == name:
                return c
        raise KeyError(name)

    def index_of(self, name: str) -> int:
        return self.by_name(name).index


def _normalize(text: str) -> str:
    """Minúsculas + só alfanumérico separado por espaço (p/ casar nomes de ícone)."""
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text.lower()).split())


@lru_cache(maxsize=1)
def load_taxonomy(path: str | None = None) -> Taxonomy:
    p = Path(path) if path else MAPEAMENTO_PATH
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    raw = data["classes"]
    classes: list[CanonicalClass] = []
    for i, (name, spec) in enumerate(raw.items()):
        dfd = spec["dfd_type"]
        if dfd not in VALID_DFD_TYPES:
            raise ValueError(f"classe {name}: dfd_type inválido {dfd!r}")
        for s in spec.get("stride", []):
            if s not in VALID_STRIDE:
                raise ValueError(f"classe {name}: STRIDE inválido {s!r}")
        classes.append(
            CanonicalClass(
                index=i,
                name=name,
                dfd_type=dfd,
                stride=list(spec.get("stride", [])),
                aws=list(spec.get("aws", [])),
                azure=list(spec.get("azure", [])),
                gcp=list(spec.get("gcp", [])),
                labels=list(spec.get("labels", [])),
                cpe_hints=list(spec.get("cpe_hints", [])),
            )
        )
    if not classes:
        raise ValueError("mapeamento.yaml não tem classes")
    return Taxonomy(classes=classes)


def match_icon_filename(filename: str, cloud: str, taxo: Taxonomy | None = None) -> str | None:
    """Mapeia o nome de um arquivo de ícone oficial à classe canônica.

    `cloud` é "aws" ou "azure". Retorna o nome canônico ou None se nenhum
    sinônimo casar. Escolhe o sinônimo mais ESPECÍFICO (mais longo) entre os que
    aparecem como substring do nome normalizado — evita que "user" ganhe de
    "simple queue service" por acidente.
    """
    taxo = taxo or load_taxonomy()
    norm = _normalize(filename)
    best: tuple[int, str] | None = None  # (tamanho do match, classe)
    for c in taxo.classes:
        for syn in getattr(c, cloud):
            ns = _normalize(syn)
            if ns and ns in norm and (best is None or len(ns) > best[0]):
                best = (len(ns), c.name)
    return best[1] if best else None


def match_label(text: str, taxo: Taxonomy | None = None) -> str | None:
    """Caminho por OCR: mapeia um rótulo de texto livre à classe canônica."""
    taxo = taxo or load_taxonomy()
    norm = _normalize(text)
    if not norm:
        return None
    best: tuple[int, str] | None = None
    for c in taxo.classes:
        for syn in c.labels:
            ns = _normalize(syn)
            if ns and (ns in norm or norm in ns) and (best is None or len(ns) > best[0]):
                best = (len(ns), c.name)
    return best[1] if best else None


if __name__ == "__main__":
    t = load_taxonomy()
    print(f"{t.nc} classes canônicas:")
    for c in t.classes:
        print(f"  {c.index:2d}  {c.yolo_name:18s}  {c.dfd_type:14s}  STRIDE={len(c.stride)}")
