"""The Apps screen: everything in the registry."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from dig.screens.base import ScrollableScreen
from dig.storage import App, Store
from dig.theme.tokens import Palette
from dig.ui.widgets import TextButton, eyebrow

EMPTY_TEXT = (
    "No apps yet. Promote an idea from the Ideas screen, or add one here."
)


class Chip(QLabel):
    """A square-cornered mono outline. Never a filled pill."""

    def __init__(self, text: str, shipped: bool = False, parent: QWidget | None = None):
        super().__init__(text.upper(), parent)
        self.setObjectName("ChipShipped" if shipped else "Chip")
        font = self.font()
        font.setLetterSpacing(font.SpacingType.PercentageSpacing, 112)
        self.setFont(font)


class AppRow(QWidget):
    """One app on one line, with its open counts."""

    opened = Signal(int)

    def __init__(
        self,
        app: App,
        open_features: int,
        open_bugs: int,
        palette: Palette,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.app = app
        self.tokens = palette
        self._hovered = False

        self.setObjectName("AppRow")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 14, 8, 14)
        row.setSpacing(14)

        name = QLabel(app.name)
        name.setObjectName("RowTitle")
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(name, 0, Qt.AlignmentFlag.AlignVCenter)

        if app.shipped:
            chip = Chip("Shipped", shipped=True)
            chip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            row.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)

        counts = QLabel(f"{open_features} features open · {open_bugs} bugs open")
        counts.setObjectName("RowWhen")
        counts.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(counts, 0, Qt.AlignmentFlag.AlignVCenter)

        gist = QLabel(app.description.replace("\n", " ").strip())
        gist.setObjectName("RowGist")
        gist.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        metrics = gist.fontMetrics()
        self._full_gist = app.description.replace("\n", " ").strip()
        self._gist_label = gist
        gist.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row.addWidget(gist, 1, Qt.AlignmentFlag.AlignVCenter)

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        metrics = self._gist_label.fontMetrics()
        self._gist_label.setText(
            metrics.elidedText(
                self._full_gist,
                Qt.TextElideMode.ElideRight,
                max(0, self._gist_label.width()),
            )
        )

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        if self._hovered or self.hasFocus():
            painter.fillRect(self.rect(), QColor(self.tokens.surface_raised))
        painter.fillRect(
            0, self.height() - 1, self.width(), 1, QColor(self.tokens.seam)
        )
        painter.end()

    def enterEvent(self, event: QEvent) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.opened.emit(self.app.id)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.opened.emit(self.app.id)
            event.accept()
            return
        super().keyPressEvent(event)


class AppsScreen(ScrollableScreen):
    """The registry."""

    app_opened = Signal(int)
    new_app_requested = Signal()

    def __init__(self, store: Store, palette: Palette, parent: QWidget | None = None):
        super().__init__(store, palette, parent)
        self._rows: list[AppRow] = []

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)
        header.addWidget(eyebrow("Apps", section=True))
        header.addStretch(1)
        new_app = TextButton("+ New app", "LinkAccent")
        new_app.clicked.connect(self.new_app_requested)
        header.addWidget(new_app)
        self.column.addLayout(header)
        self.column.addSpacing(10)

        self.rows_holder = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_holder)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(0)
        self.column.addWidget(self.rows_holder)

        self.empty = QLabel(EMPTY_TEXT)
        self.empty.setObjectName("EmptyState")
        self.column.addWidget(self.empty)

        self.column.addStretch(1)

    def refresh(self) -> None:
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows = []

        apps = self.store.list_apps()
        for app in apps:
            open_features, open_bugs = self.store.open_counts(app.id)
            row = AppRow(app, open_features, open_bugs, self.tokens)
            row.opened.connect(self.app_opened)
            self.rows_layout.addWidget(row)
            self._rows.append(row)

        self.empty.setVisible(not apps)
        self.rows_holder.setVisible(bool(apps))

    def set_palette(self, palette: Palette) -> None:
        super().set_palette(palette)
        self.refresh()
