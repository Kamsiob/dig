"""Settings: how it looks, and where the data lives. Nothing else in v1."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from dig import paths
from dig.screens.base import ScrollableScreen
from dig.storage import Store
from dig.theme.tokens import Palette
from dig.ui.attachments import open_with_the_system
from dig.ui.rail import Segmented
from dig.ui.widgets import TextButton, eyebrow


class SettingsScreen(ScrollableScreen):
    """Two things, and a plain statement of what Dig does with your data."""

    appearance_picked = Signal(str)

    def __init__(self, store: Store, palette: Palette, parent: QWidget | None = None):
        super().__init__(store, palette, parent)

        self.column.addWidget(eyebrow("Settings", section=True))
        self.column.addSpacing(28)

        # Appearance
        self.column.addWidget(_label("Appearance"))
        self.column.addSpacing(8)
        appearance_row = QHBoxLayout()
        appearance_row.setContentsMargins(0, 0, 0, 0)
        appearance_row.setSpacing(0)
        self.segmented = Segmented()
        self.segmented.setFixedWidth(280)
        self.segmented.set_palette(palette)
        self.segmented.picked.connect(self.appearance_picked)
        appearance_row.addWidget(self.segmented, 0, Qt.AlignmentFlag.AlignLeft)
        appearance_row.addStretch(1)
        self.column.addLayout(appearance_row)
        self.column.addSpacing(10)

        following = QLabel("System follows the desktop, and changes with it.")
        following.setObjectName("EditorMeta")
        self.column.addWidget(following)
        self.column.addSpacing(40)

        # Data folder
        self.column.addWidget(_label("Data folder"))
        self.column.addSpacing(8)
        folder_row = QHBoxLayout()
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.setSpacing(16)

        self.folder_path = QLabel(str(paths.data_dir()))
        self.folder_path.setObjectName("FolderPath")
        self.folder_path.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        folder_row.addWidget(self.folder_path, 1, Qt.AlignmentFlag.AlignVCenter)

        self.open_folder = TextButton("Open folder", "GhostButton")
        self.open_folder.clicked.connect(self._open_folder)
        folder_row.addWidget(self.open_folder, 0, Qt.AlignmentFlag.AlignVCenter)

        self.column.addLayout(folder_row)
        self.column.addSpacing(10)

        promise = QLabel(
            "Your ideas, apps and attachments live here and nowhere else. "
            "Dig makes no network calls, keeps no account, and collects nothing."
        )
        promise.setObjectName("EditorMeta")
        promise.setWordWrap(True)
        self.column.addWidget(promise)

        self.column.addStretch(1)

    def set_mode(self, mode: str) -> None:
        """Keep in step with the control in the rail."""
        self.segmented.set_mode(mode)

    def refresh(self) -> None:
        self.folder_path.setText(str(paths.data_dir()))

    def _open_folder(self) -> None:
        folder = paths.ensure_data_dirs()
        open_with_the_system(folder)

    def set_palette(self, palette: Palette) -> None:
        super().set_palette(palette)
        self.segmented.set_palette(palette)


def _label(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("FieldLabel")
    font = label.font()
    font.setLetterSpacing(font.SpacingType.PercentageSpacing, 114)
    label.setFont(font)
    return label
