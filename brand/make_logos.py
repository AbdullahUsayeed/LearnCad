# SPDX-License-Identifier: LGPL-2.1-or-later
"""Generate LearnCad logo PNGs and the Windows icon."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "png"
OUT.mkdir(parents=True, exist_ok=True)
FONT_BOLD = "C:/Windows/Fonts/segoeuib.ttf"
FONT_SEMI = "C:/Windows/Fonts/segoeuisl.ttf"
FONT_REGULAR = "C:/Windows/Fonts/segoeui.ttf"

ORANGE = (255, 122, 24, 255)
AMBER = (255, 179, 71, 255)
WHITE = (245, 245, 245, 255)
BLACK = (8, 8, 8, 255)
MUTED = (155, 176, 198, 255)
MUTED_LIGHT = (91, 100, 112, 255)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.truetype(FONT_BOLD, size)


def spaced(draw, xy, text, fnt, fill, spacing):
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=fnt, fill=fill, anchor="ls")
        x += draw.textlength(char, font=fnt) + spacing
    return x


def mark(size: int, mono: bool = False) -> Image.Image:
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = s / 64.0
    border = WHITE if mono else ORANGE
    legs = WHITE
    accent = WHITE if mono else AMBER
    d.rounded_rectangle(
        [2 * u, 2 * u, 62 * u, 62 * u],
        radius=14 * u,
        fill=None if mono else BLACK,
        outline=border,
        width=max(1, int(2 * u)),
    )
    d.ellipse([27 * u, 12 * u, 37 * u, 22 * u], fill=border)
    width = max(2, int(4.5 * u))
    d.line([(29.5 * u, 22.5 * u), (18 * u, 50 * u)], fill=legs, width=width)
    d.line([(34.5 * u, 22.5 * u), (46 * u, 50 * u)], fill=legs, width=width)
    d.arc([20 * u, 34 * u, 44 * u, 52 * u], start=200, end=340, fill=accent, width=max(2, int(3 * u)))
    d.ellipse([15.2 * u, 47.2 * u, 20.8 * u, 52.8 * u], fill=border)
    d.ellipse([43.2 * u, 47.2 * u, 48.8 * u, 52.8 * u], fill=border)
    return img.resize((size, size), Image.LANCZOS)


def horizontal(width=600, height=168, light=False, mono=False):
    scale = 4
    w, h = width * scale, height * scale
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = mark(64 * scale, mono=mono)
    img.paste(m, (0, int(10 * scale)), m)
    bold = font(FONT_BOLD, int(38 * scale))
    tag_font = font(FONT_SEMI, int(9.5 * scale))
    main = (10, 10, 10, 255) if light and not mono else WHITE
    if mono:
        main = WHITE
    cad = WHITE if mono else ORANGE
    x = int(84 * scale)
    y = int(46 * scale)
    for char in "Learn":
        d.text((x, y), char, font=bold, fill=main, anchor="ls")
        x += d.textlength(char, font=bold) - int(1.2 * scale)
    for char in "Cad":
        d.text((x, y), char, font=bold, fill=cad, anchor="ls")
        x += d.textlength(char, font=bold) - int(1.2 * scale)
    tag_color = (214, 220, 228, 255) if mono else (MUTED_LIGHT if light else MUTED)
    spaced(d, (int(86 * scale), int(64 * scale)), "LEARN BY BUILDING", tag_font, tag_color, int(2.4 * scale))
    return img.resize((width, height), Image.LANCZOS)


def stacked(width=520, height=440):
    scale = 4
    w, h = width * scale, height * scale
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = mark(200 * scale)
    img.paste(m, (int((width - 200) / 2 * scale), 0), m)
    bold = font(FONT_BOLD, int(80 * scale))
    tag_font = font(FONT_SEMI, int(18 * scale))
    text = "LearnCad"
    total = sum(d.textlength(ch, font=bold) for ch in text) - int(2.8 * scale) * (len(text) - 1)
    x = (w - total) / 2
    y = int(340 * scale)
    for index, char in enumerate(text):
        d.text((x, y), char, font=bold, fill=ORANGE if index >= 5 else WHITE, anchor="ls")
        x += d.textlength(char, font=bold) - int(2.8 * scale)
    tag = "LEARN BY BUILDING"
    total_tag = sum(d.textlength(ch, font=tag_font) for ch in tag) + int(6 * scale) * (len(tag) - 1)
    spaced(d, ((w - total_tag) / 2, int(382 * scale)), tag, tag_font, MUTED, int(6 * scale))
    return img.resize((width, height), Image.LANCZOS)


def main() -> None:
    mark(512).save(OUT / "logo-mark.png")
    horizontal().save(OUT / "logo-horizontal.png")
    horizontal(light=True).save(OUT / "logo-horizontal-light.png")
    horizontal(mono=True).save(OUT / "logo-horizontal-mono.png")
    stacked().save(OUT / "logo-stacked.png")
    ico = mark(256)
    ico.save(OUT / "learncad.ico", format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("logo assets written to", OUT)


if __name__ == "__main__":
    main()
