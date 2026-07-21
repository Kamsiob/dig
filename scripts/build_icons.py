#!/usr/bin/env python3
"""Draw the app icon and render it to every size a Linux desktop wants.

The identity is the wordmark's: expedition paper, a sketched contour, and the
gold cross that marks the spot. The cross is the only thing that has to read at
16 pixels, so it carries the icon.

    .venv/bin/python scripts/build_icons.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ICONS = ROOT / "assets" / "icons"
SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

# Light palette values, so the icon reads the same on any desktop theme.
PAPER = "#F5EFE1"
EDGE = "#D9CFB6"
INK = "#33372A"
GOLD = "#A97A16"
COPPER = "#A5572E"

ICON_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="{PAPER}"/>
  <rect x="8" y="8" width="496" height="496" fill="none"
        stroke="{EDGE}" stroke-width="10"/>

  <!-- A scrap of coastline, the way the map behind Home is drawn -->
  <g fill="none" stroke="{INK}" stroke-opacity="0.20" stroke-width="9"
     stroke-linecap="round" stroke-linejoin="round">
    <path d="M74 150 C 128 104, 226 112, 268 158 S 250 268, 176 274
             S 50 222, 74 150 Z"/>
    <path d="M330 392 l 26 -38 l 26 38 M 372 392 l 20 -28 l 20 28"/>
  </g>

  <!-- The dashed route, the only dashed thing in the identity -->
  <path d="M120 196 C 200 262, 226 322, 300 330"
        fill="none" stroke="{GOLD}" stroke-opacity="0.42"
        stroke-width="10" stroke-dasharray="22 24" stroke-linecap="round"/>

  <!-- X marks the spot -->
  <g transform="rotate(-6 344 300)" stroke="{GOLD}" stroke-width="46"
     stroke-linecap="round">
    <path d="M286 242 L 402 358"/>
    <path d="M402 242 L 286 358"/>
  </g>

  <!-- The two-tone rule from the wordmark -->
  <rect x="74" y="436" width="228" height="18" fill="{GOLD}"/>
  <rect x="320" y="436" width="118" height="18" fill="{COPPER}"/>
</svg>
"""


def main() -> int:
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    ICONS.mkdir(parents=True, exist_ok=True)
    master = ICONS / "dig.svg"
    master.write_text(ICON_SVG, encoding="utf-8")
    print(f"  {master.relative_to(ROOT)}")

    app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(QByteArray(ICON_SVG.encode("utf-8")))
    if not renderer.isValid():
        raise SystemExit("The icon SVG did not parse.")

    for size in SIZES:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter)
        painter.end()
        out = ICONS / f"dig-{size}.png"
        image.save(str(out))
        print(f"  {out.relative_to(ROOT)}")

    _ = app
    return 0


if __name__ == "__main__":
    sys.exit(main())
