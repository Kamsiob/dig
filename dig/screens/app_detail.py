"""App Detail: the app, its two sheets, its notes, and everything attached."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from dig import timefmt
from dig.screens.apps import Chip
from dig.screens.base import ScrollableScreen
from dig.storage import App, BUG, FEATURE, Store
from dig.theme.tokens import Palette
from dig.ui.attachments import AttachmentSection, open_with_the_system
from dig.ui.dialogs import ConfirmDialog
from dig.ui.sheets import SheetPanel
from dig.ui.widgets import TextButton, WrappedLabel, eyebrow
from dig.ui.work import run_off_thread

SAVE_DEBOUNCE_MS = 400


class AppDetailScreen(ScrollableScreen):
    """One app, in full."""

    back_requested = Signal()
    deleted = Signal(int)
    changed = Signal()

    def __init__(self, store: Store, palette: Palette, parent: QWidget | None = None):
        super().__init__(store, palette, parent)
        self.app: App | None = None
        self._loading = False

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self.save_now)

        back = TextButton("← All apps", "BackLink")
        back.clicked.connect(self.back_requested)
        self.column.addWidget(back)
        self.column.addSpacing(16)

        # Header: the name edits in place, with its chips beside it.
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(14)

        self.name_field = QLineEdit()
        self.name_field.setObjectName("EditorTitle")
        self.name_field.setPlaceholderText("Untitled app")
        self.name_field.textEdited.connect(self._queue_save)
        head.addWidget(self.name_field, 1, Qt.AlignmentFlag.AlignVCenter)

        self.shipped_chip = Chip("Shipped", shipped=True)
        self.shipped_chip.setVisible(False)
        head.addWidget(self.shipped_chip, 0, Qt.AlignmentFlag.AlignVCenter)

        self.version_chip = Chip("")
        self.version_chip.setVisible(False)
        head.addWidget(self.version_chip, 0, Qt.AlignmentFlag.AlignVCenter)

        self.column.addLayout(head)
        self.column.addSpacing(10)

        self.description_field = QTextEdit()
        self.description_field.setObjectName("DetailDescription")
        self.description_field.setPlaceholderText("What does it do?")
        self.description_field.setFixedHeight(64)
        self.description_field.textChanged.connect(self._queue_save)
        self.column.addWidget(self.description_field)
        self.column.addSpacing(12)

        # Meta row: the GitHub link, then the fields that edit inline.
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(22)

        # One control, not two: the field is the link. It edits in place and
        # the button beside it hands the address to the browser.
        self.github_field = QLineEdit()
        self.github_field.setObjectName("MetaLinkField")
        self.github_field.setPlaceholderText("GitHub URL")
        self.github_field.textEdited.connect(self._queue_save)
        meta_row.addWidget(self.github_field, 1, Qt.AlignmentFlag.AlignVCenter)

        self.github_link = TextButton("open ↗", "MetaLink")
        self.github_link.setToolTip("Open this in the browser")
        self.github_link.clicked.connect(self._open_github)
        self.github_link.setVisible(False)
        meta_row.addWidget(self.github_link, 0, Qt.AlignmentFlag.AlignVCenter)

        self.version_field = QLineEdit()
        self.version_field.setObjectName("MetaField")
        self.version_field.setPlaceholderText("Version")
        self.version_field.setFixedWidth(120)
        self.version_field.textEdited.connect(self._queue_save)
        meta_row.addWidget(self.version_field, 0, Qt.AlignmentFlag.AlignVCenter)

        self.shipped_toggle = TextButton("Mark shipped", "MetaToggle")
        self.shipped_toggle.clicked.connect(self._toggle_shipped)
        meta_row.addWidget(self.shipped_toggle, 0, Qt.AlignmentFlag.AlignVCenter)

        self.column.addLayout(meta_row)
        self.column.addSpacing(20)

        # Origin: the thread back to the jot it came from.
        self.origin = QWidget()
        self.origin.setObjectName("OriginCallout")
        self.origin.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        origin_layout = QVBoxLayout(self.origin)
        origin_layout.setContentsMargins(16, 12, 16, 12)
        origin_layout.setSpacing(4)
        self.origin_tag = QLabel("")
        self.origin_tag.setObjectName("OriginTag")
        origin_tag_font = self.origin_tag.font()
        origin_tag_font.setLetterSpacing(
            origin_tag_font.SpacingType.PercentageSpacing, 114
        )
        self.origin_tag.setFont(origin_tag_font)
        origin_layout.addWidget(self.origin_tag)
        self.origin_text = WrappedLabel("")
        self.origin_text.setObjectName("OriginText")
        origin_layout.addWidget(self.origin_text)
        self.origin.setVisible(False)
        self.column.addWidget(self.origin)

        # Sheets, side by side.
        self.column.addSpacing(34)
        sheets = QHBoxLayout()
        sheets.setContentsMargins(0, 0, 0, 0)
        sheets.setSpacing(28)
        self.features = SheetPanel(store, FEATURE, palette)
        self.features.changed.connect(self.changed)
        sheets.addWidget(self.features, 1, Qt.AlignmentFlag.AlignTop)
        self.bugs = SheetPanel(store, BUG, palette)
        self.bugs.changed.connect(self.changed)
        sheets.addWidget(self.bugs, 1, Qt.AlignmentFlag.AlignTop)
        self.column.addLayout(sheets)

        # Notes
        self.column.addSpacing(34)
        self.column.addWidget(eyebrow("Notes & talking points", section=True))
        self.column.addSpacing(10)
        self.notes_field = QTextEdit()
        self.notes_field.setObjectName("EditorNote")
        self.notes_field.setPlaceholderText(
            "What to say about it, and what to remember."
        )
        self.notes_field.setMinimumHeight(140)
        self.notes_field.textChanged.connect(self._queue_save)
        self.column.addWidget(self.notes_field)

        # Screenshots
        self.column.addSpacing(34)
        self.column.addWidget(eyebrow("Screenshots", section=True))
        self.column.addSpacing(10)
        self.screenshots = AttachmentSection(store, images=True, palette=palette)
        self.column.addWidget(self.screenshots)

        # Attachments
        self.column.addSpacing(34)
        self.column.addWidget(eyebrow("Attachments", section=True))
        self.column.addSpacing(10)
        self.attachments = AttachmentSection(store, images=False, palette=palette)
        self.column.addWidget(self.attachments)

        # Deleting the app itself
        self.column.addSpacing(40)
        self.delete_button = TextButton("Delete this app", "QuietDanger")
        self.delete_button.clicked.connect(self._delete_app)
        self.column.addWidget(self.delete_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.column.addStretch(1)

    # ---------- loading ----------

    def load(self, app_id: int) -> None:
        app = self.store.get_app(app_id)
        if app is None:
            self.back_requested.emit()
            return
        self.app = app
        self._loading = True
        self.name_field.setText(app.name)
        self.description_field.setPlainText(app.description)
        self.github_field.setText(app.github_url)
        self.version_field.setText(app.version_label)
        self.notes_field.setPlainText(app.notes)
        self._loading = False

        self._refresh_chips()
        self._refresh_origin()
        self.features.load(app.id)
        self.bugs.load(app.id)
        self.screenshots.load(app.id)
        self.attachments.load(app.id)

    def refresh(self) -> None:
        if self.app is None:
            return
        self.features.refresh()
        self.bugs.refresh()
        self.screenshots.refresh()
        self.attachments.refresh()
        self._refresh_chips()

    def _refresh_chips(self) -> None:
        if self.app is None:
            return
        self.shipped_chip.setVisible(self.app.shipped)
        self.shipped_toggle.setText(
            "Unmark shipped" if self.app.shipped else "Mark shipped"
        )
        version = self.app.version_label.strip()
        self.version_chip.setText(version.upper())
        self.version_chip.setVisible(bool(version))

        self.github_link.setVisible(bool(self.app.github_url.strip()))

    def _refresh_origin(self) -> None:
        """Only shown when this app was dug out of an idea."""
        if self.app is None or self.app.origin_idea_id is None:
            self.origin.setVisible(False)
            return
        idea = self.store.get_idea(self.app.origin_idea_id)
        if idea is None:
            self.origin.setVisible(False)
            return
        self.origin_tag.setText(
            f"DUG FROM AN IDEA · JOTTED {timefmt.on_date(idea.created_at).upper()}"
        )
        self.origin_text.setText(
            f'"{idea.title}" — promoted {timefmt.on_date(self.app.created_at)}.'
        )
        self.origin.setVisible(True)

    # ---------- saving ----------

    def _queue_save(self) -> None:
        if self._loading or self.app is None:
            return
        self._save_timer.start()

    def save_now(self) -> None:
        self._save_timer.stop()
        if self.app is None:
            return
        name = self.name_field.text().strip()
        if not name:
            # An app must keep a name; an empty field reverts on save.
            name = self.app.name
            self.name_field.setText(name)

        fields = {
            "name": name,
            "description": self.description_field.toPlainText().strip(),
            "github_url": self.github_field.text().strip(),
            "version_label": self.version_field.text().strip(),
            "notes": self.notes_field.toPlainText(),
        }
        current = {
            "name": self.app.name,
            "description": self.app.description,
            "github_url": self.app.github_url,
            "version_label": self.app.version_label,
            "notes": self.app.notes,
        }
        if fields == current:
            return
        self.store.update_app(self.app.id, **fields)
        refreshed = self.store.get_app(self.app.id)
        if refreshed is not None:
            self.app = refreshed
        self._refresh_chips()
        self.changed.emit()

    def leaving(self) -> None:
        self.save_now()

    # ---------- actions ----------

    def _toggle_shipped(self) -> None:
        if self.app is None:
            return
        self.store.update_app(self.app.id, shipped=not self.app.shipped)
        refreshed = self.store.get_app(self.app.id)
        if refreshed is not None:
            self.app = refreshed
        self._refresh_chips()
        self.changed.emit()

    def _open_github(self) -> None:
        """Hand the link to the browser. Dig itself never fetches anything."""
        if self.app is None:
            return
        url = self.app.github_url.strip()
        if not url:
            return
        if "://" not in url:
            url = f"https://{url}"
        open_in_browser(url)

    def _delete_app(self) -> None:
        if self.app is None:
            return
        attachments = self.store.list_attachments(self.app.id)
        warning = f"Delete {self.app.name}?"
        if attachments:
            warning += (
                f" Its {len(attachments)} attached "
                f"{'file' if len(attachments) == 1 else 'files'} are deleted too."
            )
        else:
            warning += " Its features and bugs go with it."
        if not ConfirmDialog.ask(self, self.tokens, warning, confirm_label="Delete"):
            return

        app_id = self.app.id
        self._save_timer.stop()
        self.app = None
        self.delete_button.setEnabled(False)
        self.delete_button.setText("deleting…")

        # The rows go here, on the thread that owns the database connection.
        # Clearing the folder can be slow, so that part goes to a worker.
        folder = self.store.forget_app(app_id)

        def clear_the_folder() -> int:
            self.store.discard_folder(folder)
            return app_id

        def finished(_result: object) -> None:
            self.delete_button.setEnabled(True)
            self.delete_button.setText("Delete this app")
            self.deleted.emit(app_id)

        run_off_thread(clear_the_folder, finished)

    def set_palette(self, palette: Palette) -> None:
        super().set_palette(palette)
        self.features.set_palette(palette)
        self.bugs.set_palette(palette)
        self.screenshots.set_palette(palette)
        self.attachments.set_palette(palette)


def open_in_browser(url: str) -> bool:
    """Open a link in the desktop's browser."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    return QDesktopServices.openUrl(QUrl(url))
