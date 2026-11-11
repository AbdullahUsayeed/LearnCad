# SPDX-License-Identifier: LGPL-2.1-or-later
"""Generate LearnCad app icon candidates, PNG sizes, and Windows .ico files.

Run from the repository root:

    python brand/make_app_icon.py

Outputs go to brand/app-icon/. Nothing is overwritten in the shipping paths.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "app-icon"

ORANGE = (255, 122, 24, 255)
AMBER = (255, 179, 71, 255)
WHITE = (245, 245, 245, 255)
INK_TOP = (24, 24, 26, 255)
INK_BOTTOM = (6, 6, 7, 255)

SIZES = [16, 24, 32, 48, 64, 128, 256, 512, 1024]
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def _vertical_gradient(size: int, top: tuple, bottom: tuple) -> Image.Image:
    image = Image.new("RGBA", (size, size), top)
    draw = ImageDraw.Draw(image)
    for y in range(size):
        t = y / max(1, size - 1)
        color = tuple(_lerp(top[i], bottom[i], t) for i in range(4))
        draw.line([(0, y), (size, y)], fill=color)
    return image


def _tile(size: int, inset: float = 0.0, radius: float = 0.225) -> Image.Image:
    """Rounded dark app tile with a subtle orange rim."""
    image = _vertical_gradient(size, INK_TOP, INK_BOTTOM)
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    margin = int(size * inset)
    draw.rounded_rectangle(
        [margin, margin, size - margin - 1, size - margin - 1],
        radius=int(size * radius),
        fill=255,
    )
    image.putalpha(mask)

    rim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rim_draw = ImageDraw.Draw(rim)
    rim_draw.rounded_rectangle(
        [margin + size * 0.018, margin + size * 0.018, size - margin - 1 - size * 0.018, size - margin - 1 - size * 0.018],
        radius=max(1, int(size * (radius - 0.015))),
        outline=(255, 122, 24, 150),
        width=max(1, int(size * 0.012)),
    )
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        [size * 0.08, size * 0.55, size * 0.92, size * 1.20],
        fill=(255, 122, 24, 38),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.06))
    image.alpha_composite(glow)
    image.alpha_composite(rim)
    image.putalpha(Image.composite(image.getchannel("A"), Image.new("L", (size, size), 0), mask))
    return image


def _thick_line(draw: ImageDraw.ImageDraw, points, width: int, fill) -> None:
    draw.line(points, fill=fill, width=width, joint="curve")
    radius = width // 2
    for x, y in (points[0], points[-1]):
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=fill)


def candidate_compass(size: int) -> Image.Image:
    """Refined version of the LearnCad drafting-compass mark."""
    scale = 4
    s = size * scale
    image = _tile(s)
    draw = ImageDraw.Draw(image)
    u = s / 64.0

    def p(x: float, y: float) -> tuple[float, float]:
        return (x * u, y * u)

    draw.ellipse([p(25.5, 9.5), p(38.5, 22.5)], fill=ORANGE)
    draw.ellipse([p(29, 13), p(35, 19)], fill=(255, 210, 160, 255))
    _thick_line(draw, [p(29.4, 22.0), p(16.5, 50.0)], int(5.4 * u), WHITE)
    _thick_line(draw, [p(34.6, 22.0), p(47.5, 50.0)], int(5.4 * u), WHITE)
    draw.arc(
        [p(18.5, 31.0), p(45.5, 54.0)],
        start=200,
        end=340,
        fill=AMBER,
        width=int(3.6 * u),
    )
    draw.ellipse([p(13.2, 46.7), p(19.8, 53.3)], fill=ORANGE)
    draw.ellipse([p(44.2, 46.7), p(50.8, 53.3)], fill=ORANGE)
    return image.resize((size, size), Image.LANCZOS)


def candidate_monogram(size: int) -> Image.Image:
    """Bold L monogram measured by an orange caliper arc."""
    scale = 4
    s = size * scale
    image = _tile(s)
    draw = ImageDraw.Draw(image)
    u = s / 64.0

    def p(x: float, y: float) -> tuple[float, float]:
        return (x * u, y * u)

    radius = int(3.2 * u)
    draw.rounded_rectangle([p(18.5, 16.0), p(30.5, 47.5)], radius=radius, fill=WHITE)
    draw.rounded_rectangle([p(18.5, 35.0), p(46.0, 47.5)], radius=radius, fill=WHITE)
    draw.arc(
        [p(28.0, 15.0), p(55.5, 42.5)],
        start=305,
        end=95,
        fill=ORANGE,
        width=int(4.6 * u),
    )
    for angle_y in (20.5, 37.0):
        draw.rounded_rectangle(
            [p(50.0, angle_y - 0.9), p(56.5, angle_y + 0.9)],
            radius=int(0.9 * u),
            fill=AMBER,
        )
    return image.resize((size, size), Image.LANCZOS)


def candidate_isometric(size: int) -> Image.Image:
    """Extruded L-block: the learning-by-building idea in one solid."""
    scale = 4
    s = size * scale
    image = _tile(s)
    draw = ImageDraw.Draw(image)
    u = s / 64.0

    def p(x: float, y: float) -> tuple[float, float]:
        return (x * u, y * u)

    front = [p(20, 44), p(20, 23), p(31, 23), p(31, 35), p(45, 35), p(45, 44)]
    top = [p(20, 23), p(29, 14), p(40, 14), p(40, 26), p(31, 35), p(31, 23)]
    side = [p(31, 35), p(40, 26), p(54, 26), p(54, 35), p(45, 44), p(31, 44)]
    draw.polygon(top, fill=(255, 179, 71, 255))
    draw.polygon(side, fill=(214, 92, 12, 255))
    draw.polygon(front, fill=ORANGE)
    draw.line(front + [front[0]], fill=(255, 205, 150, 160), width=max(1, int(0.8 * u)), joint="curve")
    return image.resize((size, size), Image.LANCZOS)


CANDIDATES = {
    "learncad-app-compass": candidate_compass,
    "learncad-app-monogram": candidate_monogram,
    "learncad-app-block": candidate_isometric,
}


def _contact_sheet(paths: list[Path], target: Path) -> None:
    dark = Image.new("RGBA", (1120, 760), (10, 10, 12, 255))
    light = Image.new("RGBA", (1120, 300), (240, 241, 243, 255))
    draw = ImageDraw.Draw(dark)
    draw.text((32, 20), "LearnCad app icon candidates", fill=WHITE)
    for row, path in enumerate(paths):
        image = Image.open(path).convert("RGBA")
        y = 60 + row * 230
        draw.text((32, y + 90), path.stem, fill=(180, 190, 200, 255))
        dark.alpha_composite(image.resize((192, 192), Image.LANCZOS), (32, y))
        for index, size in enumerate((128, 64, 48, 32, 24, 16)):
            small = image.resize((size, size), Image.LANCZOS)
            dark.alpha_composite(small, (300 + index * 130, y + 90 - size // 2))

    sheet = Image.new("RGBA", (1120, 1060), (10, 10, 12, 255))
    sheet.alpha_composite(dark, (0, 0))
    sheet.alpha_composite(light, (0, 760))
    light_draw = ImageDraw.Draw(sheet)
    light_draw.text((32, 780), "On light background", fill=(20, 20, 20, 255))
    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGBA")
        sheet.alpha_composite(image.resize((128, 128), Image.LANCZOS), (32 + index * 360, 830))
        sheet.alpha_composite(image.resize((48, 48), Image.LANCZOS), (180 + index * 360, 870))
        sheet.alpha_composite(image.resize((16, 16), Image.LANCZOS), (240 + index * 360, 886))
    sheet.convert("RGB").save(target)
    print(f"wrote {target}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    preview_paths = []
    for name, factory in CANDIDATES.items():
        master = factory(1024)
        master.save(OUT / f"{name}-1024.png")
        for size in SIZES:
            factory(size).save(OUT / f"{name}-{size}.png")
        ico = factory(256)
        ico.save(OUT / f"{name}.ico", format="ICO", sizes=ICO_SIZES)
        preview_paths.append(OUT / f"{name}-1024.png")
        print(f"wrote {name} (png sizes + .ico)")
    _contact_sheet(preview_paths, OUT / "learncad-app-preview.png")


if __name__ == "__main__":
    main()
