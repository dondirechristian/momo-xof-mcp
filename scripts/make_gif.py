"""
Fabrique `docs/demo.gif` à partir d'une exécution réelle de `scripts/demo.py`.

Pourquoi ce script plutôt qu'une capture d'écran : le GIF se régénère d'une
commande quand la démonstration change, et son contenu vient d'une vraie
exécution du serveur, jamais d'un texte recopié à la main.

    python scripts/demo.py --fast > transcript.txt
    python scripts/make_gif.py transcript.txt
    python scripts/make_gif.py transcript.txt --preview   # une image PNG

Dépendance : Pillow. C'est un outil de fabrication de documentation, pas une
dépendance du paquet — il n'est volontairement pas déclaré dans
`pyproject.toml`. L'installer à la demande :

    pip install pillow
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "demo.gif"

FONT_PATH = r"C:\Windows\Fonts\consola.ttf"
FONT_BOLD = r"C:\Windows\Fonts\consolab.ttf"
FONT_SIZE = 15

PADDING = 18
VISIBLE_ROWS = 30
FPS = 10

BACKGROUND = "#0d1117"
DEFAULT = "#c9d1d9"
DIM = "#3d444d"
TITLE = "#f0f6fc"
PROMPT = "#58a6ff"
MONEY = "#ff7b72"
SAFE = "#3fb950"
WARN = "#e3b341"
VALUE = "#a5d6ff"

# Consolas ne possède pas le glyphe U+26A0. Il s'afficherait en carré vide,
# ce qui est pire que la substitution.
SUBSTITUTIONS = {"⚠": "!"}


def colour_for(line: str) -> str:
    stripped = line.strip()
    if set(stripped) == {"─"}:
        return DIM
    if "DÉPLACE DE L'ARGENT" in line:
        return MONEY
    if "lecture seule" in line or "REFUSÉ" in line:
        return SAFE
    if stripped.startswith("!") or "ne veut PAS dire" in line or "pas encore payé" in line:
        return WARN
    if stripped.startswith(">"):
        return PROMPT
    if stripped[:2].rstrip(".").isdigit() and stripped.endswith("?"):
        return TITLE
    if stripped and stripped[0].isdigit() and ". " in stripped[:4]:
        return TITLE
    if line.startswith("      ") and "  " in stripped:
        return VALUE
    return DEFAULT


def is_bold(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped and stripped[0].isdigit() and ". " in stripped[:4])


def hold_frames(line: str) -> int:
    """Combien d'images tenir après cette ligne, pour laisser le temps de lire."""
    stripped = line.strip()
    if is_bold(line):
        return 6
    if "ne veut PAS dire" in line or "pas encore payé" in line:
        return 10
    if "Zéro supposition" in line:
        return 18
    if stripped.startswith(">"):
        return 4
    return 2


def render(lines: list[str], font, bold, width: int, height: int, char_w: float,
           line_h: int) -> Image.Image:
    image = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(image)
    for row, line in enumerate(lines[-VISIBLE_ROWS:]):
        text = line
        for source, target in SUBSTITUTIONS.items():
            text = text.replace(source, target)
        draw.text(
            (PADDING, PADDING + row * line_h),
            text,
            font=bold if is_bold(line) else font,
            fill=colour_for(line),
        )
    return image


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage : python scripts/make_gif.py <transcript.txt> [--preview]")

    transcript = Path(sys.argv[1])
    preview = "--preview" in sys.argv

    # utf-8-sig et non utf-8 : PowerShell écrit un BOM en tête, que `strip()`
    # ne considère pas comme un blanc. Sans cela la première image du GIF est
    # vide, ce qui fait une mauvaise vignette sur GitHub.
    raw = transcript.read_text(encoding="utf-8-sig").splitlines()
    # On retire les lignes vides de tête et de queue, pas celles du milieu qui
    # aèrent la mise en page.
    while raw and not raw[0].strip():
        raw.pop(0)
    while raw and not raw[-1].strip():
        raw.pop()

    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    bold = ImageFont.truetype(FONT_BOLD, FONT_SIZE)

    char_w = font.getlength("M")
    line_h = FONT_SIZE + 6
    columns = max(len(line) for line in raw)
    width = int(PADDING * 2 + columns * char_w) + 4
    height = PADDING * 2 + VISIBLE_ROWS * line_h

    if preview:
        image = render(raw, font, bold, width, height, char_w, line_h)
        target = transcript.with_suffix(".preview.png")
        image.save(target)
        print(f"aperçu : {target}  ({width}x{height})")
        return

    frames: list[Image.Image] = []
    for index in range(1, len(raw) + 1):
        image = render(raw[:index], font, bold, width, height, char_w, line_h)
        frames.extend([image] * hold_frames(raw[index - 1]))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=int(1000 / FPS),
        loop=0,
        optimize=True,
    )

    size_mb = OUTPUT.stat().st_size / 1_048_576
    print(f"{OUTPUT}  —  {len(frames)} images, {width}x{height}, {size_mb:.2f} Mo")
    if size_mb > 3:
        print("ATTENTION : au-delà de 3 Mo, GitHub le chargera lentement.")


if __name__ == "__main__":
    main()
