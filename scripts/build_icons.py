#!/usr/bin/env python3
"""Draw Dig's icon.

DESIGN says: a rounded square, 22% radius, in the action blue, carrying a simple
white upward step arrow made of three ascending bars. SVG master, then PNGs at
every size the desktop asks for.

    python scripts/build_icons.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

BLUE = "#2457F5"
SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

# A 512 unit canvas. The radius is 22% of the side, as DESIGN asks.
# Three bars climbing left to right: the step arrow that stands for stages.
SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <title>Dig</title>
  <rect width="512" height="512" rx="113" ry="113" fill="{blue}"/>
  <g fill="#FFFFFF">
    <rect x="112" y="304" width="76" height="96" rx="26"/>
    <rect x="218" y="216" width="76" height="184" rx="26"/>
    <rect x="324" y="112" width="76" height="288" rx="26"/>
  </g>
</svg>
"""


def write_svg(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(SVG.format(blue=BLUE), encoding="utf-8")
    return target


def rasterize(svg_path: Path, out_dir: Path) -> list[Path]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(str(svg_path))
    written = []
    for size in SIZES:
        image = QImage(QSize(size, size), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        renderer.render(painter)
        painter.end()
        target = out_dir / f"dig-{size}.png"
        image.save(str(target))
        written.append(target)
    del app
    return written


def main() -> int:
    out_dir = REPO / "assets" / "icons"
    svg = write_svg(out_dir / "dig.svg")
    written = rasterize(svg, out_dir)
    print(f"wrote {svg.relative_to(REPO)}")
    for path in written:
        print(f"wrote {path.relative_to(REPO)} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
