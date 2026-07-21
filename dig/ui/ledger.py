"""The ledger row: how every idea is listed, on Home and on the Ideas screen.

Rows, not cards. A mono timestamp, the title in Fraunces, a dimmed one-line
gist that truncates, and a promote action that appears on hover or focus.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from dig import timefmt
from dig.storage import Idea
from dig.theme.tokens import Palette
from dig.ui.widgets import TextButton

PROMOTE_TEXT = "→ make it an app"


class LedgerRow(QWidget):
    """One idea on one line."""

    opened = Signal(int)
    promote_requested = Signal(int)
    delete_requested = Signal(int)

    def __init__(
        self,
        idea: Idea,
        palette: Palette,
        show_delete: bool = False,
        read_only: bool = False,
        suffix: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.idea = idea
        self.tokens = palette
        self._read_only = read_only
        self._hovered = False

        self.setObjectName("LedgerRow")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if not read_only:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 14, 8, 14)
        row.setSpacing(16)

        self.when = QLabel(timefmt.relative(idea.created_at))
        self.when.setObjectName("RowWhen")
        self.when.setMinimumWidth(64)
        self.when.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        row.addWidget(self.when, 0, Qt.AlignmentFlag.AlignVCenter)

        self.title = QLabel(idea.title)
        self.title.setObjectName("RowTitleDim" if read_only else "RowTitle")
        self.title.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        row.addWidget(self.title, 0, Qt.AlignmentFlag.AlignVCenter)

        if suffix:
            self.suffix = QLabel(suffix)
            self.suffix.setObjectName("RowSuffix")
            row.addWidget(self.suffix, 0, Qt.AlignmentFlag.AlignVCenter)

        self.gist = _ElidedLabel(idea.note.replace("\n", " ").strip())
        self.gist.setObjectName("RowGist")
        row.addWidget(self.gist, 1, Qt.AlignmentFlag.AlignVCenter)

        self.promote: TextButton | None = None
        self.remove: TextButton | None = None
        if not read_only:
            self.promote = TextButton(PROMOTE_TEXT, "RowPromote")
            self.promote.clicked.connect(
                lambda: self.promote_requested.emit(self.idea.id)
            )
            self.promote.setVisible(False)
            row.addWidget(self.promote, 0, Qt.AlignmentFlag.AlignVCenter)

            if show_delete:
                self.remove = TextButton("×", "RowDelete")
                self.remove.setToolTip("Delete this idea")
                self.remove.clicked.connect(
                    lambda: self.delete_requested.emit(self.idea.id)
                )
                self.remove.setVisible(False)
                row.addWidget(self.remove, 0, Qt.AlignmentFlag.AlignVCenter)

    # ---------- appearance ----------

    def set_palette(self, palette: Palette) -> None:
        self.tokens = palette
        self.update()

    def _set_actions_visible(self, visible: bool) -> None:
        if self.promote is not None:
            self.promote.setVisible(visible)
        if self.remove is not None:
            self.remove.setVisible(visible)

    def paintEvent(self, _event: object) -> None:
        """Hover background and the seam beneath, drawn rather than styled.

        A stylesheet background on the row would sit on top of the highlight
        flash a freshly kept idea uses.
        """
        painter = QPainter(self)
        if self._hovered or self.hasFocus():
            painter.fillRect(self.rect(), QColor(self.tokens.surface_raised))
        seam = QColor(self.tokens.seam)
        painter.fillRect(0, self.height() - 1, self.width(), 1, seam)
        painter.end()

    # ---------- interaction ----------

    def enterEvent(self, event: QEvent) -> None:
        self._hovered = True
        self._set_actions_visible(not self._read_only)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._hovered = False
        if not self.hasFocus():
            self._set_actions_visible(False)
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event: QEvent) -> None:
        self._set_actions_visible(not self._read_only)
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event: QEvent) -> None:
        if not self._hovered:
            self._set_actions_visible(False)
        self.update()
        super().focusOutEvent(event)

    def mouseReleaseEvent(self, event: QEvent) -> None:
        if self._read_only:
            return
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.opened.emit(self.idea.id)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._read_only:
            super().keyPressEvent(event)
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.opened.emit(self.idea.id)
            event.accept()
            return
        super().keyPressEvent(event)


class _ElidedLabel(QLabel):
    """A one-line label that trails off rather than wrapping or stretching."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setText(text)

    def setText(self, text: str) -> None:
        self._full = text
        super().setText(text)
        self._elide()

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        if not self._full:
            return
        metrics = self.fontMetrics()
        elided = metrics.elidedText(
            self._full, Qt.TextElideMode.ElideRight, max(0, self.width())
        )
        if elided != super().text():
            super().setText(elided)
