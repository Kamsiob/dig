"""The app editor: used blank for a new app, pre-filled when promoting an idea."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from dig import timefmt
from dig.screens.base import ScrollableScreen
from dig.storage import Idea, Store, StoreError
from dig.theme.tokens import Palette
from dig.ui.widgets import TextButton, eyebrow


def _field_label(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("FieldLabel")
    font = label.font()
    font.setLetterSpacing(font.SpacingType.PercentageSpacing, 114)
    label.setFont(font)
    return label


class AppEditorScreen(ScrollableScreen):
    """Create an app, either from scratch or dug out of an idea."""

    cancelled = Signal()
    created = Signal(int)

    def __init__(self, store: Store, palette: Palette, parent: QWidget | None = None):
        super().__init__(store, palette, parent)
        self.origin_idea: Idea | None = None

        self.back = TextButton("← All apps", "BackLink")
        self.back.clicked.connect(self.cancelled)
        self.column.addWidget(self.back)
        self.column.addSpacing(16)

        self.heading = QLabel("New app")
        self.heading.setObjectName("H1")
        self.column.addWidget(self.heading)
        self.column.addSpacing(8)

        self.origin_note = QLabel("")
        self.origin_note.setObjectName("EditorMeta")
        self.origin_note.setWordWrap(True)
        self.origin_note.setVisible(False)
        self.column.addWidget(self.origin_note)
        self.column.addSpacing(24)

        self.column.addWidget(_field_label("Name"))
        self.column.addSpacing(6)
        self.name_field = QLineEdit()
        self.name_field.setObjectName("FormField")
        self.name_field.setPlaceholderText("What is it called?")
        self.name_field.textChanged.connect(self._sync_enabled)
        self.column.addWidget(self.name_field)
        self.column.addSpacing(18)

        self.column.addWidget(_field_label("Description"))
        self.column.addSpacing(6)
        self.description_field = QTextEdit()
        self.description_field.setObjectName("FormArea")
        self.description_field.setPlaceholderText("What does it do?")
        self.description_field.setFixedHeight(110)
        self.column.addWidget(self.description_field)
        self.column.addSpacing(18)

        self.column.addWidget(_field_label("GitHub URL"))
        self.column.addSpacing(6)
        self.github_field = QLineEdit()
        self.github_field.setObjectName("FormField")
        self.github_field.setPlaceholderText("https://github.com/…")
        self.column.addWidget(self.github_field)
        self.column.addSpacing(18)

        self.column.addWidget(_field_label("Version label"))
        self.column.addSpacing(6)
        self.version_field = QLineEdit()
        self.version_field.setObjectName("FormField")
        self.version_field.setPlaceholderText("v1.0.0, or whatever you call it")
        self.column.addWidget(self.version_field)
        self.column.addSpacing(20)

        self.shipped_box = QCheckBox("Shipped")
        self.shipped_box.setObjectName("ShippedToggle")
        self.column.addWidget(self.shipped_box)
        self.column.addSpacing(28)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(14)
        self.create_button = TextButton("Create app", "PrimaryButton")
        self.create_button.clicked.connect(self._create)
        actions.addWidget(self.create_button, 0, Qt.AlignmentFlag.AlignVCenter)
        cancel = TextButton("Cancel", "GhostButton")
        cancel.clicked.connect(self.cancelled)
        actions.addWidget(cancel, 0, Qt.AlignmentFlag.AlignVCenter)
        actions.addStretch(1)
        self.column.addLayout(actions)
        self.column.addStretch(1)

        self._sync_enabled()

    # ---------- loading ----------

    def start_blank(self) -> None:
        """+ New app: nothing pre-filled."""
        self.origin_idea = None
        self.heading.setText("New app")
        self.origin_note.setVisible(False)
        self._clear()
        self.name_field.setFocus()

    def start_from_idea(self, idea_id: int) -> None:
        """Promote: the idea's title and note lead the way in."""
        idea = self.store.get_idea(idea_id)
        if idea is None:
            self.cancelled.emit()
            return
        self.origin_idea = idea
        self.heading.setText("Make it an app")
        self.origin_note.setText(
            f"Dug from an idea jotted {timefmt.on_date(idea.created_at)}. "
            f"The idea stays as this app's origin."
        )
        self.origin_note.setVisible(True)
        self._clear()
        self.name_field.setText(idea.title)
        self.description_field.setPlainText(idea.note)
        self.name_field.setFocus()
        self.name_field.selectAll()

    def _clear(self) -> None:
        self.name_field.clear()
        self.description_field.clear()
        self.github_field.clear()
        self.version_field.clear()
        self.shipped_box.setChecked(False)
        self._sync_enabled()

    def _sync_enabled(self) -> None:
        """An app needs a name before it can exist."""
        self.create_button.setEnabled(bool(self.name_field.text().strip()))

    # ---------- creating ----------

    def _create(self) -> None:
        name = self.name_field.text().strip()
        if not name:
            return
        description = self.description_field.toPlainText().strip()
        github = self.github_field.text().strip()
        version = self.version_field.text().strip()
        shipped = self.shipped_box.isChecked()

        try:
            if self.origin_idea is not None:
                app = self.store.promote_idea(
                    self.origin_idea.id,
                    name=name,
                    description=description,
                    github_url=github,
                    version_label=version,
                    shipped=shipped,
                )
            else:
                app = self.store.create_app(
                    name=name,
                    description=description,
                    github_url=github,
                    version_label=version,
                    shipped=shipped,
                )
        except StoreError:
            return
        self.origin_idea = None
        self.created.emit(app.id)
