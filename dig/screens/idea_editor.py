"""The idea editor: a screen, not a modal. Edits save themselves."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QTextEdit, QWidget

from dig import timefmt
from dig.screens.base import ScrollableScreen
from dig.storage import Idea, Store
from dig.theme.tokens import Palette
from dig.ui.dialogs import ConfirmDialog
from dig.ui.widgets import TextButton

SAVE_DEBOUNCE_MS = 400

DELETE_QUESTION = "Bury it for good? This can't be undug."


class IdeaEditorScreen(ScrollableScreen):
    """One idea, open for editing. There is no Save button because there is no
    moment where an edit is not already kept."""

    back_requested = Signal()
    promote_requested = Signal(int)
    deleted = Signal(int)

    def __init__(self, store: Store, palette: Palette, parent: QWidget | None = None):
        super().__init__(store, palette, parent)
        self.idea: Idea | None = None
        self._loading = False

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self.save_now)

        back = TextButton("← All ideas", "BackLink")
        back.clicked.connect(self.back_requested)
        self.column.addWidget(back)
        self.column.addSpacing(16)

        self.title_field = QLineEdit()
        self.title_field.setObjectName("EditorTitle")
        self.title_field.setPlaceholderText("Untitled idea")
        self.title_field.textEdited.connect(self._queue_save)
        self.column.addWidget(self.title_field)
        self.column.addSpacing(6)

        self.meta = QLabel("")
        self.meta.setObjectName("EditorMeta")
        self.column.addWidget(self.meta)
        self.column.addSpacing(22)

        self.note_field = QTextEdit()
        self.note_field.setObjectName("EditorNote")
        self.note_field.setPlaceholderText("Everything else about it…")
        self.note_field.setMinimumHeight(220)
        self.note_field.textChanged.connect(self._queue_save)
        self.column.addWidget(self.note_field)
        self.column.addSpacing(26)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(16)

        self.promote_button = TextButton("→ make it an app", "PrimaryButton")
        self.promote_button.clicked.connect(self._promote)
        actions.addWidget(self.promote_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.delete_button = TextButton("Delete", "QuietDanger")
        self.delete_button.clicked.connect(self._delete)
        actions.addWidget(self.delete_button, 0, Qt.AlignmentFlag.AlignVCenter)

        actions.addStretch(1)
        self.column.addLayout(actions)
        self.column.addStretch(1)

    # ---------- loading ----------

    def load(self, idea_id: int) -> None:
        """Open an idea for editing."""
        idea = self.store.get_idea(idea_id)
        if idea is None:
            self.back_requested.emit()
            return
        self.idea = idea
        self._loading = True
        self.title_field.setText(idea.title)
        self.note_field.setPlainText(idea.note)
        self._loading = False
        self._refresh_meta()
        self.title_field.setFocus()

    def _refresh_meta(self) -> None:
        if self.idea is None:
            return
        parts = [f"jotted {timefmt.on_date(self.idea.created_at)}"]
        if self.idea.last_opened_at:
            parts.append(f"last opened {timefmt.relative(self.idea.last_opened_at)}")
        else:
            parts.append("never opened since")
        self.meta.setText(" · ".join(parts))

    def refresh(self) -> None:
        if self.idea is not None:
            self._refresh_meta()

    # ---------- saving ----------

    def _queue_save(self) -> None:
        if self._loading or self.idea is None:
            return
        self._save_timer.start()

    def save_now(self) -> None:
        """Write the current text. Safe to call at any time."""
        self._save_timer.stop()
        if self.idea is None:
            return
        title = self.title_field.text().strip()
        note = self.note_field.toPlainText().strip()
        if title == self.idea.title and note == self.idea.note:
            return
        self.store.update_idea(self.idea.id, title, note)
        refreshed = self.store.get_idea(self.idea.id)
        if refreshed is not None:
            self.idea = refreshed

    def leaving(self) -> None:
        """Called before navigating away, so nothing in flight is lost."""
        self.save_now()

    # ---------- actions ----------

    def _promote(self) -> None:
        self.save_now()
        if self.idea is not None:
            self.promote_requested.emit(self.idea.id)

    def _delete(self) -> None:
        if self.idea is None:
            return
        if not ConfirmDialog.ask(
            self, self.tokens, DELETE_QUESTION, confirm_label="Bury it"
        ):
            return
        self._save_timer.stop()
        idea_id = self.idea.id
        self.store.delete_idea(idea_id)
        self.idea = None
        self.deleted.emit(idea_id)
