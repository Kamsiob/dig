"""The two things drawn behind everything: paper grain and the treasure map.

Both are whisper quiet and must never compete with content. The map appears on
Home only; the grain covers the whole window.
"""

from __future__ import annotations

import random

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from dig.theme.tokens import Palette

GRAIN_TILE = 128
GRAIN_OPACITY = 0.05
GRAIN_SEED = 20260721  # fixed so the paper looks the same every launch

_grain_tile: QPixmap | None = None


def grain_tile() -> QPixmap:
    """A tileable speck of paper texture, built once and reused."""
    global _grain_tile
    if _grain_tile is not None and not _grain_tile.isNull():
        return _grain_tile

    rng = random.Random(GRAIN_SEED)
    image = QImage(GRAIN_TILE, GRAIN_TILE, QImage.Format.Format_ARGB32_Premultiplied)
    # One pass of high-frequency noise, which is what the reference texture
    # amounts to at this opacity.
    raw = bytearray(GRAIN_TILE * GRAIN_TILE * 4)
    for i in range(0, len(raw), 4):
        value = rng.randint(0, 255)
        raw[i] = value
        raw[i + 1] = value
        raw[i + 2] = value
        raw[i + 3] = 255
    image = QImage(
        bytes(raw),
        GRAIN_TILE,
        GRAIN_TILE,
        QImage.Format.Format_ARGB32_Premultiplied,
    ).copy()
    _grain_tile = QPixmap.fromImage(image)
    return _grain_tile


class GrainOverlay(QWidget):
    """Paper texture over the whole window. Never takes a click."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setOpacity(GRAIN_OPACITY)
        painter.drawTiledPixmap(self.rect(), grain_tile())
        painter.end()


# The map, straight from design/dig-design.html: island contours, mountains,
# a river, wind gusts with curled ends, a dashed route to a bold X, and a
# planted shovel. {ink} draws the linework, {accent} the route, X and blade.
MAP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 820 720" fill="none">
  <g stroke="{ink}" stroke-opacity="{ink_op}" stroke-width="1.2" fill="none">
    <path d="M60 120 C 110 84, 190 92, 224 130 S 210 214, 150 218 S 40 180, 60 120 Z"/>
    <path d="M84 132 C 120 106, 176 112, 200 140 S 188 196, 148 198 S 62 172, 84 132 Z"/>
    <path d="M560 480 C 620 440, 720 452, 748 508 S 700 610, 620 600 S 508 532, 560 480 Z"/>
    <path d="M588 494 C 634 464, 706 474, 726 514 S 690 582, 630 574 S 546 532, 588 494 Z"/>
    <path d="M420 640 C 450 600, 430 560, 470 520 S 510 460, 495 420"/>
  </g>
  <g stroke="{ink}" stroke-opacity="{ink_op}" stroke-width="1.2" stroke-linejoin="round" fill="none">
    <path d="M300 262 l 18 -28 l 18 28 M 328 262 l 14 -21 l 14 21 M 352 262 l 11 -16 l 11 16"/>
    <path d="M318 244 l 6 9"/>
    <path d="M620 210 l 16 -24 l 16 24 M 646 210 l 12 -18 l 12 18 M 668 210 l 9 -13 l 9 13"/>
    <path d="M120 420 l 15 -22 l 15 22 M 144 420 l 11 -16 l 11 16"/>
    <path d="M210 560 l 14 -20 l 14 20 M 232 560 l 10 -15 l 10 15 M 250 560 l 8 -12 l 8 12"/>
  </g>
  <g stroke="{ink}" stroke-opacity="{ink_op}" stroke-width="1.2" stroke-linecap="round" fill="none">
    <path d="M470 150 C 530 138, 590 138, 640 150 c 14 4, 14 18, 0 20 c -10 1, -14 -8, -6 -12"/>
    <path d="M450 180 C 520 168, 580 168, 622 178 c 11 3, 11 14, 0 16 c -8 1, -11 -6, -5 -9"/>
    <path d="M90 320 C 150 308, 210 308, 258 318 c 12 3, 12 15, 0 17 c -9 1, -12 -7, -5 -10"/>
    <path d="M540 620 C 600 608, 650 608, 692 618 c 11 3, 11 14, 0 16 c -8 1, -11 -6, -5 -9"/>
  </g>
  <path d="M140 170 C 260 240, 300 380, 420 400 S 620 380, 668 528"
        stroke="{accent}" stroke-opacity="{accent_op}" stroke-width="1.6" stroke-dasharray="7 8" fill="none"/>
  <g stroke="{accent}" stroke-opacity="{accent_op}" stroke-width="3" stroke-linecap="round" fill="none">
    <path d="M658 518 l 22 22 M 680 518 l -22 22"/>
  </g>
  <g stroke="{ink}" stroke-opacity="{ink_op}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none">
    <path d="M716 58 c 8 -8, 20 -8, 27 0 c 4 5, 3 12, -3 16 l -9 6"/>
    <path d="M722 66 c 5 -4, 11 -4, 14 0"/>
    <path d="M731 80 L 762 128"/>
    <path d="M754 122 c 12 -6, 24 -2, 28 8 c 4 11, -2 24, -14 30 c -8 4, -16 2, -20 -6 c -4 -9, -2 -24, 6 -32 Z"
          fill="{blade}" fill-opacity="{blade_op}"/>
    <path d="M748 168 l 5 3 M 760 172 l 6 2 M 774 170 l 5 -2"/>
  </g>
</svg>"""

MAP_VIEWBOX = (820.0, 720.0)


def _rgba_to_svg(token: str) -> tuple[str, float]:
    """Split an rgba() token into a hex-ish colour and an opacity.

    Qt's SVG renderer handles rgb() but not the alpha in rgba(), so the alpha
    is applied through the painter instead.
    """
    text = token.strip()
    if not text.startswith("rgba"):
        return text, 1.0
    inner = text[text.index("(") + 1 : text.rindex(")")]
    parts = [p.strip() for p in inner.split(",")]
    if len(parts) != 4:
        return text, 1.0
    r, g, b = (int(float(v)) for v in parts[:3])
    return f"rgb({r},{g},{b})", float(parts[3])


class MapBackdrop(QWidget):
    """The sketched treasure map behind Home. Never takes a click."""

    def __init__(self, palette: Palette, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._renderer: QSvgRenderer | None = None
        self._opacity = 1.0
        self.set_palette(palette)

    def set_palette(self, palette: Palette) -> None:
        """Rebuild the map in the colours of the palette now in force."""
        ink, ink_alpha = _rgba_to_svg(palette.map_ink)
        accent, accent_alpha = _rgba_to_svg(palette.map_accent)
        # Qt's SVG renderer ignores the alpha inside rgba(), so each element
        # carries its own stroke-opacity instead. Applying one painter-wide
        # alpha would drag the linework up to the route's strength and make
        # the map shout.
        self._opacity = 1.0
        svg = MAP_SVG.format(
            ink=ink,
            ink_op=f"{ink_alpha:.3f}",
            accent=accent,
            accent_op=f"{accent_alpha:.3f}",
            blade=accent,
            # The blade is a faint wash, not a solid shape.
            blade_op=f"{accent_alpha * 0.25:.3f}",
        )
        renderer = QSvgRenderer()
        renderer.load(svg.encode("utf-8"))
        self._renderer = renderer
        self.update()

    def paintEvent(self, _event: object) -> None:
        if self._renderer is None or not self._renderer.isValid():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self._opacity)
        self._renderer.render(painter, self._slice_rect())
        painter.end()

    def _slice_rect(self) -> QRectF:
        """Cover the widget while keeping the map's proportions, cropping the rest.

        This is what preserveAspectRatio="xMidYMid slice" does in the mockup.
        """
        vw, vh = MAP_VIEWBOX
        w = float(self.width())
        h = float(self.height())
        if w <= 0 or h <= 0:
            return QRectF(0, 0, w, h)
        scale = max(w / vw, h / vh)
        sw, sh = vw * scale, vh * scale
        return QRectF((w - sw) / 2.0, (h - sh) / 2.0, sw, sh)
