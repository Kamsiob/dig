"""Small shared building blocks used across the screens."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from dig.theme.tokens import Palette


def eyebrow(text: str, section: bool = False) -> QLabel:
    """A mono uppercase section header with wide letter spacing."""
    label = QLabel(text.upper())
    label.setObjectName("SectionEyebrow" if section else "Eyebrow")
    font = label.font()
    font.setLetterSpacing(font.SpacingType.PercentageSpacing, 115)
    label.setFont(font)
    return label


class WrappedLabel(QLabel):
    """A word-wrapped label that reserves the height its text actually needs.

    A plain wrapped QLabel reports a height derived from a width the layout has
    not settled on yet, so a second line ends up painted outside the space it
    was given. This one re-measures whenever its text or width changes.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._sync_height()

    def _sync_height(self) -> None:
        width = self.width()
        if width <= 0:
            return
        needed = self.heightForWidth(width)
        if needed > 0 and self.minimumHeight() != needed:
            self.setMinimumHeight(needed)
            self.updateGeometry()

    def setText(self, text: str) -> None:
        super().setText(text)
        self._sync_height()

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._sync_height()


class Seam(QFrame):
    """A hairline separator."""

    def __init__(self, palette: Palette, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.set_palette(palette)

    def set_palette(self, palette: Palette) -> None:
        self.setStyleSheet(f"background: {palette.seam};")


class WordmarkRule(QWidget):
    """The two-tone flat rule under the wordmark: gold, a gap, then copper.

    Two solid runs, not a fade. It is one of the only two constructions in Dig
    that puts colours side by side.
    """

    def __init__(self, palette: Palette, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(3)
        self._palette_tokens = palette

    def set_palette(self, palette: Palette) -> None:
        self._palette_tokens = palette
        self.update()

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        width = self.width()
        height = self.height()
        gold_end = int(width * 0.62)
        copper_start = int(width * 0.68)
        painter.fillRect(0, 0, gold_end, height, QColor(self._palette_tokens.accent))
        painter.fillRect(
            copper_start,
            0,
            width - copper_start,
            height,
            QColor(self._palette_tokens.copper),
        )
        painter.end()


class TiltedX(QWidget):
    """The gold ✕ of the wordmark, tilted a few degrees off square.

    Drawn rather than set as text so the tilt is real: X marks the spot, and a
    mark scratched onto a map is never perfectly upright.
    """

    TILT_DEGREES = -6.0

    def __init__(self, palette: Palette, size: int = 20, parent: QWidget | None = None):
        super().__init__(parent)
        self._size = size
        self._colour = palette.accent
        self.setFixedSize(int(size * 1.1), int(size * 1.1))

    def set_palette(self, palette: Palette) -> None:
        self._colour = palette.accent
        self.update()

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.translate(self.width() / 2.0, self.height() / 2.0)
        painter.rotate(self.TILT_DEGREES)

        reach = self._size * 0.34
        pen = painter.pen()
        pen.setColor(QColor(self._colour))
        pen.setWidthF(max(1.6, self._size * 0.11))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(int(-reach), int(-reach), int(reach), int(reach))
        painter.drawLine(int(reach), int(-reach), int(-reach), int(reach))
        painter.end()


class Wordmark(QWidget):
    """"Dig" in Fraunces with the small gold ✕ beside it. X marks the spot."""

    def __init__(
        self, palette: Palette, size: int = 40, parent: QWidget | None = None
    ):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.name = QLabel("Dig")
        self.name.setObjectName("Wordmark")
        if size != 40:
            self.name.setStyleSheet(f"font-size: {size}px;")

        self.mark = TiltedX(palette, size=int(size * 0.5))

        row.addWidget(self.name, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.mark, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addStretch(1)

    def set_palette(self, palette: Palette) -> None:
        self.mark.set_palette(palette)


class StatusLamp(QWidget):
    """The verdigris dot in the rail footer. The one round thing in Dig."""

    def __init__(self, palette: Palette, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(7, 7)
        self._colour = palette.verdigris

    def set_palette(self, palette: Palette) -> None:
        self._colour = palette.verdigris
        self.update()

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._colour))
        painter.drawEllipse(self.rect())
        painter.end()


def soft_shadow(
    widget: QWidget, palette: Palette, blur: int = 24, dy: int = 6, alpha: int = 40
) -> QGraphicsDropShadowEffect:
    """The quiet lift under a raised block. Qt stylesheets cannot do shadows."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setXOffset(0)
    effect.setYOffset(dy)
    colour = QColor(0, 0, 0) if palette.is_dark else QColor(80, 70, 40)
    colour.setAlpha(alpha)
    effect.setColor(colour)
    widget.setGraphicsEffect(effect)
    return effect


class TextButton(QPushButton):
    """A button that reads as a link: no chrome, keyboard reachable."""

    def __init__(self, text: str, object_name: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName(object_name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
