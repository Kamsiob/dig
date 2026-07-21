"""Feature and bug sheets.

A line is done or it is not. There are no priorities, no statuses, no dates on
items, no assignees, and no ordering handles. This is not a project manager.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from dig.storage import BUG, FEATURE, SheetItem, Store
from dig.theme.tokens import Palette
from dig.ui.widgets import TextButton

KIND_TITLES = {FEATURE: "Feature sheet", BUG: "Bug sheet"}
KIND_ADD = {FEATURE: "+ add feature", BUG: "+ add bug"}
KIND_PLACEHOLDER = {
    FEATURE: "What should it do?",
    BUG: "What is broken?",
}
KIND_EMPTY = {
    FEATURE: "No features yet.",
    BUG: "No bugs. Enjoy it while it lasts.",
}


class SheetLine(QWidget):
    """One line. Click anywhere to toggle it; the ✕ removes it."""

    toggled = Signal(int)
    removed = Signal(int)

    def __init__(self, item: SheetItem, palette: Palette, parent: QWidget | None = None):
        super().__init__(parent)
        self.item = item
        self.tokens = palette
        self._hovered = False

        self.setObjectName("SheetLine")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(4, 9, 4, 9)
        row.setSpacing(10)

        self.marker = QLabel("[✓]" if item.done else "[ ]")
        self.marker.setObjectName("SheetMarkerDone" if item.done else "SheetMarker")
        self.marker.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        row.addWidget(self.marker, 0, Qt.AlignmentFlag.AlignTop)

        self.text = QLabel(item.text)
        self.text.setObjectName("SheetTextDone" if item.done else "SheetText")
        self.text.setWordWrap(True)
        self.text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        if item.done:
            font = self.text.font()
            font.setStrikeOut(True)
            self.text.setFont(font)
        row.addWidget(self.text, 1)

        self.remove = TextButton("×", "SheetRemove")
        self.remove.setToolTip("Remove this line")
        self.remove.clicked.connect(lambda: self.removed.emit(self.item.id))
        self.remove.setVisible(False)
        row.addWidget(self.remove, 0, Qt.AlignmentFlag.AlignTop)

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
        self.remove.setVisible(True)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._hovered = False
        if not self.hasFocus():
            self.remove.setVisible(False)
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event: QEvent) -> None:
        self.remove.setVisible(True)
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event: QEvent) -> None:
        if not self._hovered:
            self.remove.setVisible(False)
        self.update()
        super().focusOutEvent(event)

    def mouseReleaseEvent(self, event: QEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggled.emit(self.item.id)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.toggled.emit(self.item.id)
            event.accept()
            return
        super().keyPressEvent(event)


class _AddField(QLineEdit):
    """Enter commits the line, Esc gives up on it."""

    committed = Signal(str)
    cancelled = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.committed.emit(self.text())
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class SheetPanel(QWidget):
    """One sheet: a ruled header, the lines, and a way to add another."""

    changed = Signal()

    def __init__(
        self, store: Store, kind: str, palette: Palette, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.store = store
        self.kind = kind
        self.tokens = palette
        self.app_id: int | None = None
        self._lines: list[SheetLine] = []

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        header = QWidget()
        header.setObjectName("SheetHeadFeature" if kind == FEATURE else "SheetHeadBug")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 7)
        header_row.setSpacing(12)

        title = QLabel(KIND_TITLES[kind].upper())
        title.setObjectName("SectionEyebrow")
        title_font = title.font()
        title_font.setLetterSpacing(title_font.SpacingType.PercentageSpacing, 115)
        title.setFont(title_font)
        header_row.addWidget(title, 1, Qt.AlignmentFlag.AlignBottom)

        self.count = QLabel("0 open · 0 done")
        self.count.setObjectName("SheetCount")
        header_row.addWidget(self.count, 0, Qt.AlignmentFlag.AlignBottom)
        column.addWidget(header)

        self.lines_holder = QWidget()
        self.lines_layout = QVBoxLayout(self.lines_holder)
        self.lines_layout.setContentsMargins(0, 0, 0, 0)
        self.lines_layout.setSpacing(0)
        column.addWidget(self.lines_holder)

        self.empty = QLabel(KIND_EMPTY[kind])
        self.empty.setObjectName("SheetEmpty")
        column.addWidget(self.empty)

        self.add_field = _AddField()
        self.add_field.setObjectName("SheetAddField")
        self.add_field.setPlaceholderText(KIND_PLACEHOLDER[kind])
        self.add_field.committed.connect(self._commit_new)
        self.add_field.cancelled.connect(self._cancel_add)
        self.add_field.setVisible(False)
        column.addWidget(self.add_field)

        self.add_link = TextButton(KIND_ADD[kind], "SheetAdd")
        self.add_link.clicked.connect(self.begin_add)
        column.addWidget(self.add_link, 0, Qt.AlignmentFlag.AlignLeft)
        column.addSpacing(10)

    # ---------- building ----------

    def load(self, app_id: int) -> None:
        self.app_id = app_id
        self.refresh()

    def refresh(self) -> None:
        for line in self._lines:
            line.setParent(None)
            line.deleteLater()
        self._lines = []

        if self.app_id is None:
            return

        items = self.store.list_sheet_items(self.app_id, self.kind)
        for item in items:
            line = SheetLine(item, self.tokens)
            line.toggled.connect(self._toggle)
            line.removed.connect(self._remove)
            self.lines_layout.addWidget(line)
            self._lines.append(line)

        self.empty.setVisible(not items)
        self.lines_holder.setVisible(bool(items))

        counts = self.store.sheet_counts(self.app_id, self.kind)
        self.count.setText(str(counts))

    # ---------- adding ----------

    def begin_add(self) -> None:
        """The add link becomes an input in the same place."""
        self.add_link.setVisible(False)
        self.add_field.clear()
        self.add_field.setVisible(True)
        self.add_field.setFocus()

    def _cancel_add(self) -> None:
        self.add_field.clear()
        self.add_field.setVisible(False)
        self.add_link.setVisible(True)

    def _commit_new(self, text: str) -> None:
        if self.app_id is None:
            return
        if not text.strip():
            self._cancel_add()
            return
        self.store.add_sheet_item(self.app_id, self.kind, text)
        self.add_field.clear()
        # Stay open: a run of features is usually more than one.
        self.add_field.setFocus()
        self.refresh()
        self.changed.emit()

    # ---------- editing ----------

    def _toggle(self, item_id: int) -> None:
        self.store.toggle_sheet_item(item_id)
        self.refresh()
        self.changed.emit()

    def _remove(self, item_id: int) -> None:
        """One line, one click. A mis-delete costs seconds to retype."""
        self.store.delete_sheet_item(item_id)
        self.refresh()
        self.changed.emit()

    def set_palette(self, palette: Palette) -> None:
        self.tokens = palette
        for line in self._lines:
            line.tokens = palette
            line.update()
