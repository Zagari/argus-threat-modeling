"""Indexa os ícones oficiais AWS/Azure nas classes canônicas e rasteriza p/ PNG.

Os pacotes oficiais exigem download manual (aceite de termos), então este script
NÃO baixa da internet: aponte-o para o .zip (ou a pasta já extraída) que você
baixou e ele faz o resto — casa cada SVG à classe via `mapeamento.yaml`
(palavras-chave `aws:`/`azure:`) e grava PNGs em `<out>/<classe>/`, que o
gerador (`icon_bank.py`) consome automaticamente.

Onde baixar (ver icons/README.md):
  AWS  : "AWS Architecture Icons" (Asset Package, .zip)
  Azure: "Azure architecture icons" (Azure_Public_Service_Icons_*.zip)
  GCP  : "Google Cloud icons" (cloud.google.com/icons, .zip de SVGs)

Uso:
  python training/icons/fetch_icons.py --aws-zip ~/Downloads/AWS-Icons.zip \\
         --azure-zip ~/Downloads/Azure-Icons.zip --gcp-zip ~/Downloads/GCP-Icons.zip \\
         --out data/icons
  python training/icons/fetch_icons.py --gcp-dir ~/gcp-svgs --list-unmatched
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from taxonomy.loader import load_taxonomy, match_icon_filename  # noqa: E402


def _svgs_from(source: str | None, workdir: Path) -> list[Path]:
    if not source:
        return []
    p = Path(source).expanduser()
    if p.is_dir():
        return sorted(p.rglob("*.svg"))
    if p.suffix.lower() == ".zip":
        dest = workdir / p.stem
        with zipfile.ZipFile(p) as z:
            z.extractall(dest)
        return sorted(dest.rglob("*.svg"))
    raise SystemExit(f"fonte inválida (esperado .zip ou pasta): {source}")


def _cairosvg_status() -> tuple[bool, str]:
    """(disponível, motivo). Captura ImportError (não instalado) E OSError (lib
    nativa do cairo ausente — cairocffi falha ao carregar libcairo)."""
    try:
        import cairosvg  # type: ignore  # noqa: F401
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def _rasterize(svg: Path, png: Path, size: int) -> bool:
    """Rasteriza UM SVG. Retorna False só p/ este arquivo (SVG malformado),
    sem desligar a rasterização dos demais. Pressupõe cairosvg disponível."""
    import cairosvg  # type: ignore

    try:
        cairosvg.svg2png(url=str(svg), write_to=str(png), output_width=size, output_height=size)
        return True
    except Exception:  # noqa: BLE001 — SVG específico falhou: pula só ele
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Indexa ícones oficiais → classes canônicas.")
    ap.add_argument("--aws-zip")
    ap.add_argument("--aws-dir")
    ap.add_argument("--azure-zip")
    ap.add_argument("--azure-dir")
    ap.add_argument("--gcp-zip")
    ap.add_argument("--gcp-dir")
    ap.add_argument("--out", default="data/icons")
    ap.add_argument("--size", type=int, default=256, help="lado do PNG rasterizado")
    ap.add_argument("--no-rasterize", action="store_true", help="só gera o manifest (sem PNG)")
    ap.add_argument("--list-unmatched", action="store_true", help="lista SVGs sem classe")
    args = ap.parse_args()

    taxo = load_taxonomy()
    out = Path(args.out)
    manifest: list[dict] = []
    unmatched: list[str] = []
    per_class: dict[str, int] = {c.yolo_name: 0 for c in taxo.classes}

    # decide UMA vez se dá p/ rasterizar (cairosvg + cairo nativo presentes)
    rasterize = not args.no_rasterize
    if rasterize:
        ok, reason = _cairosvg_status()
        if not ok:
            print(f"⚠ cairosvg indisponível ({reason}). Gerando só o manifest.\n"
                  "  • instale no venv ATIVO: pip install cairosvg\n"
                  "  • lib nativa do cairo (Debian/Ubuntu): sudo apt-get install -y libcairo2")
            rasterize = False

    raster_fail = 0
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        sources = [
            ("aws", _svgs_from(args.aws_zip or args.aws_dir, workdir)),
            ("azure", _svgs_from(args.azure_zip or args.azure_dir, workdir)),
            ("gcp", _svgs_from(args.gcp_zip or args.gcp_dir, workdir)),
        ]
        for cloud, svgs in sources:
            for svg in svgs:
                cls = match_icon_filename(svg.name, cloud, taxo)
                if cls is None:
                    unmatched.append(f"{cloud}: {svg.name}")
                    continue
                yname = taxo.by_name(cls).yolo_name
                folder = out / yname
                folder.mkdir(parents=True, exist_ok=True)
                png = folder / f"{cloud}_{svg.stem}.png"
                png_written = False
                if rasterize:
                    if _rasterize(svg, png, args.size):
                        png_written = True
                    else:
                        raster_fail += 1  # SVG específico falhou: pula só ele
                per_class[yname] += 1
                manifest.append({"cloud": cloud, "svg": svg.name, "class": yname,
                                 "png": str(png) if png_written else None})

    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    covered = sum(1 for v in per_class.values() if v)
    print(f"\n{len(manifest)} ícones indexados · {covered}/{taxo.nc} classes cobertas · "
          f"{len(unmatched)} sem classe")
    for name, count in per_class.items():
        flag = " " if count else "✗"
        print(f"  {flag} {name:18s} {count}")
    if rasterize and raster_fail:
        print(f"\n{raster_fail} SVG(s) não rasterizaram e foram pulados (os demais viraram PNG).")
    if args.list_unmatched and unmatched:
        print("\nSem classe (considere acrescentar sinônimos em mapeamento.yaml):")
        for u in unmatched[:120]:
            print(f"  {u}")
    if not rasterize and not args.no_rasterize:
        print("\nNenhum PNG gravado (sem cairosvg). O gerador seguirá usando glifos "
              "primitivos até os PNGs existirem.")


if __name__ == "__main__":
    main()
