"""Mises en page 10x15 (photo seule ou planche de 4) et envoi à CUPS via `lp`."""
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

import config
import settings

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]
MARGIN, GAP = 40, 20


def _font(size):
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def _canvas():
    """Fond blanc 10x15 + bandeau texte. Renvoie (image, hauteur utile)."""
    W, H = config.PRINT_SIZE_PX
    footer_text = settings.get("print_footer")
    footer = 110 if footer_text else 0
    canvas = Image.new("RGB", (W, H), "white")
    if footer:
        # replace() plutôt que format() : une accolade isolée dans le texte ne plante pas
        text = footer_text.replace("{date}", datetime.now().strftime("%d/%m/%Y"))
        ImageDraw.Draw(canvas).text((W // 2, H - MARGIN - footer // 2), text,
                                    fill=(30, 30, 30), font=_font(56), anchor="mm")
    return canvas, H - 2 * MARGIN - footer


def single_layout(img: Image.Image) -> Image.Image:
    canvas, inner_h = _canvas()
    W = canvas.width
    canvas.paste(ImageOps.fit(img, (W - 2 * MARGIN, inner_h), Image.LANCZOS), (MARGIN, MARGIN))
    return canvas


def grid_layout(images: list[Image.Image]) -> Image.Image:
    """Planche 2 colonnes (2x2 pour 4 photos)."""
    canvas, inner_h = _canvas()
    cols = 2
    rows = (len(images) + cols - 1) // cols
    cw = (canvas.width - 2 * MARGIN - GAP * (cols - 1)) // cols
    ch = (inner_h - GAP * (rows - 1)) // rows
    for i, img in enumerate(images):
        r, c = divmod(i, cols)
        # BICUBIC + reducing_gap : nettement plus rapide que LANCZOS sur Pi, rendu équivalent
        tile = ImageOps.fit(img, (cw, ch), Image.BICUBIC)
        canvas.paste(tile, (MARGIN + c * (cw + GAP), MARGIN + r * (ch + GAP)))
    return canvas


def print_file(path: Path) -> str:
    cmd = ["lp"]
    if config.PRINTER:
        cmd += ["-d", config.PRINTER]
    cmd += [*config.PRINT_OPTIONS, str(path)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "lp a échoué")
    return res.stdout.strip()


def print_session(folder: Path) -> str:
    """La planche (montage.jpg) est déjà au format 10x15 ; une photo seule est mise en page."""
    montage = folder / "montage.jpg"
    if montage.exists():
        return print_file(montage)
    out = folder / "print.jpg"
    if not out.exists():
        with Image.open(folder / "1.jpg") as img:
            single_layout(ImageOps.exif_transpose(img).convert("RGB")).save(
                out, "JPEG", quality=95, dpi=(300, 300))
    return print_file(out)
