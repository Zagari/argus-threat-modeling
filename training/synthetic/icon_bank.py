"""Banco de ícones por classe canônica, com fallback para glifo primitivo.

Prefere PNGs reais em `<icons_dir>/<yolo_name>/*.png` (produzidos por
icons/fetch_icons.py a partir dos SVGs oficiais). Se a classe não tiver ícone
real, cai no glifo primitivo de `glyphs.py`. Assim o gerador roda offline e,
quando os ícones oficiais existem, fica realista sem mudar o pipeline.
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image
from taxonomy.loader import CanonicalClass, Taxonomy

from synthetic.glyphs import render_glyph


def _fit_square(img: Image.Image, size: int) -> Image.Image:
    """Encaixa `img` (preservando proporção) num quadrado RGBA `size`×`size`."""
    img = img.convert("RGBA")
    img.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
    return canvas


class IconBank:
    def __init__(self, taxo: Taxonomy, icons_dir: Path | None = None) -> None:
        self.taxo = taxo
        self.icons_dir = Path(icons_dir) if icons_dir else None
        self._real: dict[str, list[Path]] = {}
        if self.icons_dir and self.icons_dir.is_dir():
            for c in taxo.classes:
                folder = self.icons_dir / c.yolo_name
                if folder.is_dir():
                    pngs = sorted(folder.glob("*.png"))
                    if pngs:
                        self._real[c.name] = pngs

    @property
    def real_classes(self) -> set[str]:
        return set(self._real)

    def coverage(self) -> str:
        n = len(self._real)
        total = self.taxo.nc
        return f"{n}/{total} classes com ícone real; demais usam glifo primitivo"

    def get(self, cls: CanonicalClass, size: int, rng: random.Random) -> Image.Image:
        paths = self._real.get(cls.name)
        if paths:
            chosen = paths[rng.randrange(len(paths))]
            try:
                return _fit_square(Image.open(chosen), size)
            except OSError:
                pass  # arquivo corrompido → cai no glifo
        return render_glyph(cls.yolo_name, cls.index, cls.dfd_type, size)
