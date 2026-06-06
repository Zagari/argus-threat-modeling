"""Gerador de diagramas sintéticos auto-rotulados para o detector do ARGUS (E1).

Compõe diagramas de arquitetura plausíveis amostrando ícones (reais ou glifos),
posicionando-os numa grade com jitter, desenhando setas (topologia), rótulos de
texto e fronteiras de confiança — e, como as posições são conhecidas, emite os
**labels YOLO** (`class cx cy w h` normalizado) automaticamente, além das arestas
como ground-truth de topologia (útil na Fase 5) e um `data.yaml` pronto p/ treino.

Roda offline (glifos primitivos). Com `--icons-dir` aponta p/ os PNGs reais
produzidos por icons/fetch_icons.py, ficando realista sem mudar nada.

Exemplo:
    python training/synthetic/generate_synthetic.py --n 3000 --out data/synthetic
    python training/synthetic/generate_synthetic.py --n 50 --out /tmp/ds   # sanidade
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# bootstrap: coloca training/ no path p/ rodar como script de qualquer cwd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw  # noqa: E402
from taxonomy.loader import CanonicalClass, Taxonomy, load_taxonomy  # noqa: E402

from synthetic.glyphs import _load_font as _load_label_font  # noqa: E402
from synthetic.icon_bank import IconBank  # noqa: E402

# Estilos de fundo: (cor de fundo, cor de traço p/ setas/texto, tem grade?)
BACKGROUNDS = [
    ((255, 255, 255), (40, 40, 40), False),     # branco
    ((245, 247, 250), (55, 60, 70), False),     # cinza claro
    ((247, 244, 235), (70, 65, 55), True),      # "whiteboard" creme com grade
    ((33, 37, 43), (220, 224, 230), False),     # escuro
    ((28, 32, 46), (210, 220, 240), True),      # escuro azulado com grade
]


def _make_background(w: int, h: int, style: int, rng) -> tuple[Image.Image, tuple[int, int, int]]:
    bg, stroke, grid = BACKGROUNDS[style]
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    if grid:
        step = rng.choice([48, 64, 80])
        gc = tuple(int(c * 0.92 + s * 0.08) for c, s in zip(bg, stroke, strict=True))
        for x in range(step, w, step):
            d.line((x, 0, x, h), fill=gc, width=1)
        for y in range(step, h, step):
            d.line((0, y, w, y), fill=gc, width=1)
    return img, stroke


def _draw_arrow(d: ImageDraw.ImageDraw, p1, p2, color, width: int) -> None:
    d.line((p1, p2), fill=color, width=width)
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    head = max(10, width * 4)
    for off in (math.radians(150), math.radians(-150)):
        hx = p2[0] + head * math.cos(ang + off)
        hy = p2[1] + head * math.sin(ang + off)
        d.line((p2, (hx, hy)), fill=color, width=width)


def _border_point(cx, cy, half, tx, ty):
    """Ponto na borda do quadrado (centro cx,cy, meia-aresta half) rumo a (tx,ty)."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    scale = half / max(abs(dx), abs(dy))
    return cx + dx * scale, cy + dy * scale


def _split_of(idx: int, n: int, ratios: tuple[float, float, float]) -> str:
    pos = (idx + 0.5) / n
    if pos < ratios[0]:
        return "train"
    if pos < ratios[0] + ratios[1]:
        return "val"
    return "test"


def _sample_classes(taxo: Taxonomy, k: int, rng) -> list[CanonicalClass]:
    """Amostra k classes (sem trust_boundary, que é tratada à parte), com repetição."""
    pool = [c for c in taxo.classes if c.dfd_type != "TrustBoundary"]
    return [pool[rng.randrange(len(pool))] for _ in range(k)]


def _label_text(cls: CanonicalClass, rng) -> str:
    opts = cls.labels or [cls.yolo_name]
    return opts[rng.randrange(len(opts))]


def generate_image(
    idx: int, taxo: Taxonomy, bank: IconBank, rng, *, imgsz: int,
    min_icons: int, max_icons: int, draw_edges: bool,
) -> tuple[Image.Image, list[tuple[int, float, float, float, float]], list[tuple[int, int]]]:
    """Gera uma imagem + labels YOLO (lista de (cls_idx, cx,cy,w,h) normalizados) + arestas."""
    w = int(imgsz * rng.uniform(0.85, 1.18))
    h = int(imgsz * rng.uniform(0.85, 1.18))
    style = rng.randrange(len(BACKGROUNDS))
    img, stroke = _make_background(w, h, style, rng)
    base = min(w, h)
    pad = int(base * 0.035)

    cell = base * 0.19
    cols = max(1, int((w - 2 * pad) / cell))
    rows = max(1, int((h - 2 * pad) / cell))
    capacity = cols * rows
    n_icons = min(rng.randint(min_icons, max_icons), capacity)

    free_cells = [(r, c) for r in range(rows) for c in range(cols)]
    rng.shuffle(free_cells)
    chosen_cells = free_cells[:n_icons]
    classes = _sample_classes(taxo, n_icons, rng)

    cw = (w - 2 * pad) / cols
    ch = (h - 2 * pad) / rows
    labels: list[tuple[int, float, float, float, float]] = []
    centers: list[tuple[float, float, float]] = []  # (cx, cy, half) por ícone
    overlay = ImageDraw.Draw(img)

    # fronteira de confiança (atrás dos ícones): envolve um bloco retangular de células
    if rng.random() < 0.45 and cols >= 2 and rows >= 2:
        c0, c1 = sorted(rng.sample(range(cols), 2))
        r0, r1 = sorted(rng.sample(range(rows), 2))
        bx0 = pad + c0 * cw - cw * 0.25
        by0 = pad + r0 * ch - ch * 0.25
        bx1 = pad + (c1 + 1) * cw + cw * 0.25
        by1 = pad + (r1 + 1) * ch + ch * 0.25
        bx0, by0 = max(2, bx0), max(2, by0)
        bx1, by1 = min(w - 2, bx1), min(h - 2, by1)
        dash = 14
        x = bx0
        while x < bx1:  # retângulo tracejado
            overlay.line((x, by0, min(x + dash, bx1), by0), fill=stroke, width=2)
            overlay.line((x, by1, min(x + dash, bx1), by1), fill=stroke, width=2)
            x += dash * 2
        y = by0
        while y < by1:
            overlay.line((bx0, y, bx0, min(y + dash, by1)), fill=stroke, width=2)
            overlay.line((bx1, y, bx1, min(y + dash, by1)), fill=stroke, width=2)
            y += dash * 2
        tb = taxo.by_name("trust_boundary")
        labels.append((
            tb.index, ((bx0 + bx1) / 2) / w, ((by0 + by1) / 2) / h,
            (bx1 - bx0) / w, (by1 - by0) / h,
        ))

    # ícones
    for (r, c), cls in zip(chosen_cells, classes, strict=True):
        s = int(min(cw, ch) * rng.uniform(0.5, 0.72))
        s = max(48, s)
        cell_x = pad + c * cw
        cell_y = pad + r * ch
        ix = int(cell_x + rng.uniform(0.06, 0.30) * (cw - s))
        iy = int(cell_y + rng.uniform(0.04, 0.22) * (ch - s))
        icon = bank.get(cls, s, rng)
        img.paste(icon, (ix, iy), icon)
        cx, cy = ix + s / 2, iy + s / 2
        centers.append((cx, cy, s / 2))
        labels.append((cls.index, cx / w, cy / h, s / w, s / h))
        if rng.random() < 0.75:  # rótulo de texto sob o ícone (realismo + futura OCR)
            txt = _label_text(cls, rng)
            tf = _load_label_font(max(11, int(s * 0.26)))
            tw = overlay.textlength(txt, font=tf)
            overlay.text((cx - tw / 2, iy + s + 2), txt, fill=stroke, font=tf)

    # setas (topologia)
    edges: list[tuple[int, int]] = []
    if draw_edges and len(centers) >= 2:
        n_edges = rng.randint(1, max(1, len(centers) - 1))
        for _ in range(n_edges):
            a, b = rng.randrange(len(centers)), rng.randrange(len(centers))
            if a == b:
                continue
            ca, cb = centers[a], centers[b]
            p1 = _border_point(ca[0], ca[1], ca[2], cb[0], cb[1])
            p2 = _border_point(cb[0], cb[1], cb[2], ca[0], ca[1])
            _draw_arrow(overlay, p1, p2, stroke, width=max(2, base // 480))
            edges.append((a, b))

    return img, labels, edges


def write_dataset(args: argparse.Namespace) -> dict:
    taxo = load_taxonomy(args.mapeamento)
    bank = IconBank(taxo, Path(args.icons_dir) if args.icons_dir else None)
    out = Path(args.out)
    ratios = (args.train, args.val, 1.0 - args.train - args.val)
    if ratios[2] <= 0:
        raise SystemExit("train+val devem somar < 1.0 (sobra p/ test)")

    for split in ("train", "val", "test"):
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
        if args.edges:
            (out / "edges" / split).mkdir(parents=True, exist_ok=True)

    import random as _random
    counts = {"train": 0, "val": 0, "test": 0}
    class_hist = {c.yolo_name: 0 for c in taxo.classes}
    for i in range(args.n):
        rng = _random.Random(args.seed * 1_000_003 + i)
        split = _split_of(i, args.n, ratios)
        img, labels, edges = generate_image(
            i, taxo, bank, rng, imgsz=args.imgsz,
            min_icons=args.min_icons, max_icons=args.max_icons, draw_edges=args.edges,
        )
        stem = f"img_{i:06d}"
        img.save(out / "images" / split / f"{stem}.png")
        lines = [f"{ci} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for (ci, cx, cy, w, h) in labels]
        (out / "labels" / split / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        if args.edges:
            (out / "edges" / split / f"{stem}.json").write_text(json.dumps(edges), encoding="utf-8")
        counts[split] += 1
        for (ci, *_rest) in labels:
            class_hist[taxo.classes[ci].yolo_name] += 1

    data_yaml = _write_data_yaml(out, taxo)
    meta = {
        "n": args.n,
        "seed": args.seed,
        "imgsz": args.imgsz,
        "splits": counts,
        "ratios": {"train": ratios[0], "val": ratios[1], "test": ratios[2]},
        "icon_coverage": bank.coverage(),
        "class_histogram": class_hist,
        "data_yaml": str(data_yaml),
        "nc": taxo.nc,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def _write_data_yaml(out: Path, taxo: Taxonomy) -> Path:
    names = "\n".join(f"  {c.index}: {c.yolo_name}" for c in taxo.classes)
    content = (
        f"# Gerado por generate_synthetic.py — NÃO editar à mão.\n"
        f"path: {out.resolve()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"test: images/test\n"
        f"nc: {taxo.nc}\n"
        f"names:\n{names}\n"
    )
    p = out / "data.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Gera dataset sintético YOLO p/ o detector ARGUS.")
    p.add_argument("--n", type=int, default=3000, help="número de imagens")
    p.add_argument("--out", type=str, default="data/synthetic", help="diretório de saída")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--imgsz", type=int, default=1280, help="tamanho base da tela")
    p.add_argument("--min-icons", type=int, default=4)
    p.add_argument("--max-icons", type=int, default=12)
    p.add_argument("--train", type=float, default=0.8, help="fração de treino")
    p.add_argument("--val", type=float, default=0.1, help="fração de validação")
    p.add_argument("--icons-dir", type=str, default=None, help="PNGs reais por classe (fetch_icons)")
    p.add_argument("--mapeamento", type=str, default=None, help="caminho do mapeamento.yaml")
    p.add_argument("--no-edges", dest="edges", action="store_false", help="não emitir topologia GT")
    p.set_defaults(edges=True)
    return p


def main() -> None:
    args = build_parser().parse_args()
    meta = write_dataset(args)
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
