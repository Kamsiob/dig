"""Screenshots and attachments.

Files are copied into Dig's own folder on attach, never referenced where they
sit. Removing one removes the stored copy with it.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from dig.storage import Attachment, Store
from dig.theme.tokens import Palette
from dig.ui.dialogs import ConfirmDialog
from dig.ui.widgets import TextButton
from dig.ui.work import run_off_thread

THUMB_WIDTH = 150
THUMB_HEIGHT = 94

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.tif *.tiff *.svg)"
ANY_FILTER = "All files (*)"


def readable_size(size: int) -> str:
    """A file size a person can read at a glance."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


def open_with_the_system(path: str | Path) -> bool:
    """Hand a file to whatever the desktop uses for it."""
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def confirm_removal(parent: QWidget, palette: Palette, name: str) -> bool:
    return ConfirmDialog.ask(
        parent,
        palette,
        f"Remove {name}? The stored copy is deleted too.",
        confirm_label="Remove",
    )


class Thumbnail(QWidget):
    """One screenshot, with its filename underneath."""

    open_requested = Signal(int)
    remove_requested = Signal(int)

    def __init__(
        self, attachment: Attachment, palette: Palette, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.attachment = attachment
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)

        frame = QWidget()
        frame.setObjectName("Thumb")
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        frame.setFixedSize(THUMB_WIDTH, THUMB_HEIGHT)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(1, 1, 1, 1)
        frame_layout.setSpacing(0)

        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setObjectName("ThumbImage")
        pixmap = QPixmap(attachment.stored_path)
        if pixmap.isNull():
            self.image.setText("no preview")
        else:
            self.image.setPixmap(
                pixmap.scaled(
                    THUMB_WIDTH - 2,
                    THUMB_HEIGHT - 2,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        frame_layout.addWidget(self.image)
        column.addWidget(frame)

        caption = QHBoxLayout()
        caption.setContentsMargins(0, 0, 0, 0)
        caption.setSpacing(6)

        name = QLabel(attachment.filename)
        name.setObjectName("ThumbName")
        name.setMaximumWidth(THUMB_WIDTH - 20)
        metrics = name.fontMetrics()
        name.setText(
            metrics.elidedText(
                attachment.filename, Qt.TextElideMode.ElideMiddle, THUMB_WIDTH - 24
            )
        )
        name.setToolTip(attachment.filename)
        caption.addWidget(name, 1)

        self.remove = TextButton("×", "SheetRemove")
        self.remove.setToolTip(f"Remove {attachment.filename}")
        self.remove.clicked.connect(
            lambda: self.remove_requested.emit(self.attachment.id)
        )
        self.remove.setVisible(False)
        caption.addWidget(self.remove, 0)
        column.addLayout(caption)

    def enterEvent(self, event: QEvent) -> None:
        self.remove.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        if not self.hasFocus():
            self.remove.setVisible(False)
        super().leaveEvent(event)

    def focusInEvent(self, event: QEvent) -> None:
        self.remove.setVisible(True)
        super().focusInEvent(event)

    def mouseReleaseEvent(self, event: QEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_requested.emit(self.attachment.id)
        super().mouseReleaseEvent(event)


class FileRow(QWidget):
    """One attachment that is not an image: name and size, in mono."""

    open_requested = Signal(int)
    remove_requested = Signal(int)

    def __init__(
        self, attachment: Attachment, palette: Palette, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.attachment = attachment
        self.setObjectName("FileRow")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"#FileRow {{ border-bottom: 1px solid {palette.seam}; }}")

        row = QHBoxLayout(self)
        row.setContentsMargins(4, 8, 4, 8)
        row.setSpacing(12)

        name = QLabel(attachment.filename)
        name.setObjectName("FileName")
        row.addWidget(name, 1)

        size = QLabel(readable_size(attachment.size))
        size.setObjectName("FileSize")
        row.addWidget(size, 0)

        self.remove = TextButton("×", "SheetRemove")
        self.remove.setToolTip(f"Remove {attachment.filename}")
        self.remove.clicked.connect(
            lambda: self.remove_requested.emit(self.attachment.id)
        )
        self.remove.setVisible(False)
        row.addWidget(self.remove, 0)

    def enterEvent(self, event: QEvent) -> None:
        self.remove.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        if not self.hasFocus():
            self.remove.setVisible(False)
        super().leaveEvent(event)

    def focusInEvent(self, event: QEvent) -> None:
        self.remove.setVisible(True)
        super().focusInEvent(event)

    def mouseReleaseEvent(self, event: QEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_requested.emit(self.attachment.id)
        super().mouseReleaseEvent(event)


class AttachmentSection(QWidget):
    """Either the screenshots strip or the file list, depending on `images`."""

    changed = Signal()

    def __init__(
        self,
        store: Store,
        images: bool,
        palette: Palette,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.store = store
        self.images = images
        self.tokens = palette
        self.app_id: int | None = None
        self._items: list[QWidget] = []
        self._busy = False

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)

        self.holder = QWidget()
        if images:
            self.holder_layout = QHBoxLayout(self.holder)
            self.holder_layout.setSpacing(12)
            self.holder_layout.setContentsMargins(0, 0, 0, 0)
            self.holder_layout.addStretch(1)
        else:
            self.holder_layout = QVBoxLayout(self.holder)
            self.holder_layout.setSpacing(0)
            self.holder_layout.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self.holder)

        self.empty = QLabel(
            "No screenshots yet." if images else "No attachments yet."
        )
        self.empty.setObjectName("SheetEmpty")
        column.addWidget(self.empty)

        self.add_link = TextButton("+ add", "SheetAdd")
        self.add_link.clicked.connect(self._pick_files)
        column.addWidget(self.add_link, 0, Qt.AlignmentFlag.AlignLeft)

    # ---------- building ----------

    def load(self, app_id: int) -> None:
        self.app_id = app_id
        self.refresh()

    def refresh(self) -> None:
        for item in self._items:
            item.setParent(None)
            item.deleteLater()
        self._items = []

        if self.app_id is None:
            return

        attachments = self.store.list_attachments(self.app_id, images=self.images)
        for attachment in attachments:
            widget: QWidget
            if self.images:
                widget = Thumbnail(attachment, self.tokens)
            else:
                widget = FileRow(attachment, self.tokens)
            widget.open_requested.connect(self._open)
            widget.remove_requested.connect(self._remove)
            if self.images:
                self.holder_layout.insertWidget(
                    self.holder_layout.count() - 1, widget
                )
            else:
                self.holder_layout.addWidget(widget)
            self._items.append(widget)

        self.empty.setVisible(not attachments)
        self.holder.setVisible(bool(attachments))

    # ---------- actions ----------

    def _pick_files(self) -> None:
        if self.app_id is None or self._busy:
            return
        chosen, _filter = QFileDialog.getOpenFileNames(
            self,
            "Add screenshots" if self.images else "Add attachments",
            str(Path.home()),
            IMAGE_FILTER if self.images else ANY_FILTER,
        )
        if chosen:
            self.attach_paths(chosen)

    def attach_paths(self, paths: list[str]) -> None:
        """Copy files in.

        The copying is the slow part and runs on a worker thread. Recording
        them happens back here: a sqlite3 connection belongs to the thread
        that opened it and cannot be used from another one.
        """
        if self.app_id is None or not paths:
            return
        app_id = self.app_id
        self._set_busy(True)

        def copy_them() -> list[Path]:
            return [self.store.stage_attachment(app_id, path) for path in paths]

        run_off_thread(copy_them, self._record, self._failed)

    def _record(self, stored: object) -> None:
        """Back on the main thread: write the rows for the copied files."""
        app_id = self.app_id
        if app_id is not None and isinstance(stored, list):
            for path in stored:
                self.store.record_attachment(app_id, path)
        self._set_busy(False)
        self.refresh()
        self.changed.emit()

    def _failed(self, message: str) -> None:
        self._set_busy(False)
        self.empty.setText(message)
        self.empty.setVisible(True)
        self.refresh()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.add_link.setEnabled(not busy)
        self.add_link.setText("copying…" if busy else "+ add")

    def _open(self, attachment_id: int) -> None:
        attachment = self.store.get_attachment(attachment_id)
        if attachment is not None:
            open_with_the_system(attachment.stored_path)

    def _remove(self, attachment_id: int) -> None:
        attachment = self.store.get_attachment(attachment_id)
        if attachment is None:
            return
        if not confirm_removal(self, self.tokens, attachment.filename):
            return
        self.store.delete_attachment(attachment_id)
        self.refresh()
        self.changed.emit()

    def set_palette(self, palette: Palette) -> None:
        self.tokens = palette
        self.refresh()
