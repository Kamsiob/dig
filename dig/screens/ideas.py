"""The Ideas screen: everything in the ground, newest first, with search."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from dig.screens.base import ScrollableScreen
from dig.storage import Store
from dig.theme.tokens import Palette
from dig.ui.dialogs import ConfirmDialog
from dig.ui.ledger import LedgerRow
from dig.ui.widgets import eyebrow

DELETE_QUESTION = "Bury it for good? This can't be undug."

EMPTY_TEXT = "Nothing buried yet. Jot the first one on Home."
NO_MATCH_TEXT = "Nothing matches that."


class SearchField(QLineEdit):
    """Live search. Esc clears it."""

    cleared = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self.text():
                self.clear()
                self.cleared.emit()
                event.accept()
                return
        super().keyPressEvent(event)


class IdeasScreen(ScrollableScreen):
    """The full ledger."""

    idea_opened = Signal(int)
    promote_requested = Signal(int)

    def __init__(self, store: Store, palette: Palette, parent: QWidget | None = None):
        super().__init__(store, palette, parent)
        self._rows: list[LedgerRow] = []

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)
        header.addWidget(eyebrow("Ideas", section=True))
        header.addStretch(1)
        self.column.addLayout(header)
        self.column.addSpacing(14)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(18)

        self.search = SearchField()
        self.search.setObjectName("SearchField")
        self.search.setPlaceholderText("Search ideas…")
        self.search.setClearButtonEnabled(False)
        self.search.textChanged.connect(lambda _text: self._rebuild())
        self.search.cleared.connect(self._rebuild)
        controls.addWidget(self.search, 1)

        self.show_promoted = QCheckBox("Show promoted")
        self.show_promoted.setObjectName("ShowPromoted")
        self.show_promoted.setChecked(False)
        self.show_promoted.toggled.connect(lambda _on: self._rebuild())
        controls.addWidget(self.show_promoted, 0, Qt.AlignmentFlag.AlignVCenter)

        self.column.addLayout(controls)
        self.column.addSpacing(18)

        self.rows_holder = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_holder)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(0)
        self.column.addWidget(self.rows_holder)

        self.empty = QLabel(EMPTY_TEXT)
        self.empty.setObjectName("EmptyState")
        self.column.addWidget(self.empty)

        self.column.addStretch(1)

    # ---------- building ----------

    def refresh(self) -> None:
        self._rebuild()

    def on_shown(self) -> None:
        self._rebuild()
        self.search.setFocus()

    def _rebuild(self) -> None:
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows = []

        term = self.search.text()
        include_promoted = self.show_promoted.isChecked()
        ideas = self.store.list_ideas(
            include_promoted=include_promoted, search=term
        )

        for idea in ideas:
            promoted = idea.is_promoted
            suffix = ""
            if promoted:
                app = self.store.get_app(idea.promoted_app_id or -1)
                suffix = f"→ {app.name}" if app else "→ an app"
            row = LedgerRow(
                idea,
                self.tokens,
                show_delete=not promoted,
                read_only=promoted,
                suffix=suffix,
            )
            row.opened.connect(self.idea_opened)
            row.promote_requested.connect(self.promote_requested)
            row.delete_requested.connect(self._delete)
            self.rows_layout.addWidget(row)
            self._rows.append(row)

        has_rows = bool(ideas)
        self.rows_holder.setVisible(has_rows)
        self.empty.setVisible(not has_rows)
        self.empty.setText(NO_MATCH_TEXT if term.strip() else EMPTY_TEXT)

    # ---------- actions ----------

    def _delete(self, idea_id: int) -> None:
        if not ConfirmDialog.ask(
            self, self.tokens, DELETE_QUESTION, confirm_label="Bury it"
        ):
            return
        self.store.delete_idea(idea_id)
        self._rebuild()

    def set_palette(self, palette: Palette) -> None:
        super().set_palette(palette)
        for row in self._rows:
            row.set_palette(palette)
