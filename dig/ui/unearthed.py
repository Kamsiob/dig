"""The Unearthed block: one old idea, pulled back out of the ground at random.

The signature moment of the app. A raised panel with the strata gauge down its
left edge, the specimen inside it, and two actions in the top right.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from dig import timefmt
from dig.storage import Idea
from dig.theme.tokens import Palette
from dig.ui.widgets import TextButton, WrappedLabel, soft_shadow

STRATA_WIDTH = 34
TICK_COLUMN = 6
TICK_SPACING = 12


class StrataGauge(QWidget):
    """Four stacked soil bands with a tick ruler down their right edge.

    Depth, drawn. The deepest band is copper because that is where the
    specimen came from.
    """

    def __init__(self, palette: Palette, parent: QWidget | None = None):
        super().__init__(parent)
        self.tokens = palette
        self.setFixedWidth(STRATA_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def set_palette(self, palette: Palette) -> None:
        self.tokens = palette
        self.update()

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        height = self.height()
        width = self.width()
        bands = self.tokens.strata
        band_height = height / float(len(bands))
        for index, colour in enumerate(bands):
            top = int(index * band_height)
            bottom = int((index + 1) * band_height) if index < len(bands) - 1 else height
            painter.fillRect(0, top, width, bottom - top, QColor(colour))

        # The ruler: repeating hairline marks, like a measured trench wall.
        seam = QColor(self.tokens.seam)
        x = width - TICK_COLUMN
        y = TICK_SPACING - 1
        while y < height:
            painter.fillRect(x, y, TICK_COLUMN, 1, seam)
            y += TICK_SPACING
        painter.end()


class UnearthedBlock(QFrame):
    """The specimen on display, or a quiet note when there is nothing to show."""

    open_requested = Signal(int)
    dig_again_requested = Signal()

    def __init__(self, palette: Palette, parent: QWidget | None = None):
        super().__init__(parent)
        self.tokens = palette
        self.idea: Idea | None = None

        self.setObjectName("Unearthed")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.strata = StrataGauge(palette)
        row.addWidget(self.strata)

        body = QWidget()
        body.setObjectName("UnearthedBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(26, 22, 24, 20)
        body_layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(18)

        self.tag = QLabel("")
        self.tag.setObjectName("UnearthedTag")
        tag_font = self.tag.font()
        tag_font.setLetterSpacing(tag_font.SpacingType.PercentageSpacing, 116)
        self.tag.setFont(tag_font)
        header.addWidget(self.tag, 1, Qt.AlignmentFlag.AlignVCenter)

        self.open_button = TextButton("Open it", "UnearthedOpen")
        self.open_button.clicked.connect(self._emit_open)
        header.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.again_button = TextButton("Dig again ↻", "UnearthedAgain")
        self.again_button.clicked.connect(self.dig_again_requested)
        header.addWidget(self.again_button, 0, Qt.AlignmentFlag.AlignVCenter)

        body_layout.addLayout(header)
        body_layout.addSpacing(10)

        self.title = WrappedLabel("")
        self.title.setObjectName("UnearthedTitle")
        body_layout.addWidget(self.title)
        body_layout.addSpacing(6)

        self.gist = WrappedLabel("")
        self.gist.setObjectName("UnearthedGist")
        self.gist.setMaximumWidth(620)
        body_layout.addWidget(self.gist)

        self.meta = QLabel("")
        self.meta.setObjectName("UnearthedMeta")
        body_layout.addSpacing(14)
        body_layout.addWidget(self.meta)

        row.addWidget(body, 1)
        soft_shadow(self, palette)

    # ---------- content ----------

    def show_idea(self, idea: Idea) -> None:
        """Put a specimen on display."""
        self.idea = idea
        self.tag.setText(f"UNEARTHED · {timefmt.buried(idea.created_at).upper()}")
        self.title.setText(idea.title)

        gist = idea.note.replace("\n", " ").strip()
        self.gist.setText(gist)
        self.gist.setVisible(bool(gist))
        self.updateGeometry()

        meta = f"jotted {timefmt.on_date(idea.created_at)}"
        if idea.never_opened:
            meta += " · never opened since"
        self.meta.setText(meta)
        self.meta.setVisible(True)

        self.open_button.setVisible(True)
        self.again_button.setVisible(True)

    def show_empty(self) -> None:
        """Nothing is old enough yet. The gauge stays; the actions do not."""
        self.idea = None
        self.tag.setText("UNEARTHED")
        self.title.setText("Nothing old enough to unearth yet.")
        self.gist.setText("Keep jotting.")
        self.gist.setVisible(True)
        self.meta.setVisible(False)
        self.open_button.setVisible(False)
        self.again_button.setVisible(False)

    def set_palette(self, palette: Palette) -> None:
        self.tokens = palette
        self.strata.set_palette(palette)
        soft_shadow(self, palette)

    def _emit_open(self) -> None:
        if self.idea is not None:
            self.open_requested.emit(self.idea.id)
