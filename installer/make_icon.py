# SPDX-License-Identifier: LGPL-2.1-or-later
"""Build the Windows installer icon from the LearnCad brand mark."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "brand" / "png" / "logo-mark.png"
TARGET = Path(__file__).with_name("assets") / "learncad.ico"


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Missing brand mark: {SOURCE}")
    image = Image.open(SOURCE).convert("RGBA")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        TARGET,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"wrote {TARGET} ({TARGET.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
