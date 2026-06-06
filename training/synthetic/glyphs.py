"""Glifos primitivos determinísticos — fallback offline do gerador sintético.

Quando os ícones oficiais AWS/Azure não estão disponíveis (CI, primeira execução),
cada classe canônica é desenhada como uma forma simples (cor + monograma) cujo
formato segue o tipo DFD. Isso permite gerar o dataset e treinar uma versão
"de forma" do detector totalmente offline; com os ícones reais (via fetch_icons.py)
o realismo aumenta, mas o pipeline é idêntico.
"""

from __future__ import annotations

import colorsys
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
]


@lru_cache(maxsize=64)
def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:  # Pillow >= 10 aceita tamanho na fonte default
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _palette(index: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """(cor de preenchimento clara, cor de borda escura) determinística por índice."""
    hue = (index * 0.137) % 1.0  # passo áureo-ish → cores bem espalhadas
    fr, fg, fb = colorsys.hls_to_rgb(hue, 0.78, 0.55)
    br, bg, bb = colorsys.hls_to_rgb(hue, 0.38, 0.65)
    fill = (int(fr * 255), int(fg * 255), int(fb * 255))
    border = (int(br * 255), int(bg * 255), int(bb * 255))
    return fill, border


def _monogram(yolo_name: str) -> str:
    tokens = [t for t in yolo_name.split("_") if t]
    if len(tokens) == 1:
        return tokens[0][:3].upper()
    return "".join(t[0] for t in tokens[:3]).upper()


def render_glyph(yolo_name: str, index: int, dfd_type: str, size: int) -> Image.Image:
    """Desenha o glifo da classe num quadrado RGBA `size`×`size` (transparente)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fill, border = _palette(index)
    m = max(2, size // 16)  # margem
    lw = max(2, size // 24)  # espessura da borda
    box = (m, m, size - m, size - m)

    if dfd_type == "DataStore":
        # cilindro (banco de dados): elipse de topo + corpo + base
        ell_h = (box[3] - box[1]) // 5
        left, top, right, bottom = box
        d.rectangle((left, top + ell_h // 2, right, bottom - ell_h // 2), fill=fill)
        d.line((left, top + ell_h // 2, left, bottom - ell_h // 2), fill=border, width=lw)
        d.line((right, top + ell_h // 2, right, bottom - ell_h // 2), fill=border, width=lw)
        d.ellipse((left, bottom - ell_h, right, bottom), fill=fill, outline=border, width=lw)
        d.ellipse((left, top, right, top + ell_h), fill=fill, outline=border, width=lw)
    elif dfd_type == "ExternalEntity":
        d.rectangle(box, fill=fill, outline=border, width=lw)  # retângulo de cantos vivos
    else:  # Process e demais → retângulo arredondado
        d.rounded_rectangle(box, radius=size // 8, fill=fill, outline=border, width=lw)

    text = _monogram(yolo_name)
    font = _load_font(max(10, size // 4))
    tb = d.textbbox((0, 0), text, font=font)
    tx = (size - (tb[2] - tb[0])) // 2 - tb[0]
    ty = (size - (tb[3] - tb[1])) // 2 - tb[1]
    d.text((tx, ty), text, fill=(20, 20, 20), font=font)
    return img
