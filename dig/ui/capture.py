"""The capture dialog: one feature or bug, onto one app, without leaving anything.

Reachable from the panel on Home and with Ctrl K from any screen. The whole
flow works without touching the mouse.

The system-wide hotkey is deliberately not attempted: grabbing a global key
from inside the app does not work on Wayland. That belongs in a KDE custom
shortcut in a later version.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from dig.storage import BUG, FEATURE, Store
from dig.theme.tokens import Palette
from dig.ui.widgets import TextButton

NO_APPS_TEXT = "No apps yet. Promote an idea first, or add one on the Apps screen."

PANEL_WIDTH = 420


class KindToggle(QFrame):
    """Feature or Bug. Arrow keys move between them, as does a click."""

    picked = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Segmented")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._kind = FEATURE
        self.buttons: dict[str, TextButton] = {}
        for index, (kind, label) in enumerate(((FEATURE, "Feature"), (BUG, "Bug"))):
            button = TextButton(label, "CaptureSegment")
            button.setProperty("active", kind == FEATURE)
            button.clicked.connect(lambda _c=False, k=kind: self.set_kind(k))
            if index:
                divider = QFrame()
                divider.setFixedWidth(1)
                divider.setObjectName("SegmentDivider")
                row.addWidget(divider)
                self._divider = divider
            row.addWidget(button, 1)
            self.buttons[kind] = button

    @property
    def kind(self) -> str:
        return self._kind

    def set_kind(self, kind: str) -> None:
        if kind not in (FEATURE, BUG):
            return
        self._kind = kind
        for key, button in self.buttons.items():
            button.setProperty("active", key == kind)
            button.style().unpolish(button)
            button.style().polish(button)
        self.picked.emit(kind)

    def toggle(self) -> None:
        self.set_kind(BUG if self._kind == FEATURE else FEATURE)

    def set_palette(self, palette: Palette) -> None:
        divider = getattr(self, "_divider", None)
        if divider is not None:
            divider.setStyleSheet(f"background: {palette.seam};")


class CaptureDialog(QDialog):
    """A panel on a scrim over the window."""

    captured = Signal(int, str)
    """app id, kind"""

    def __init__(
        self,
        store: Store,
        palette: Palette,
        last_app_id: int | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.store = store
        self.tokens = palette

        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        centring = QHBoxLayout()
        centring.addStretch(1)

        self.panel = QFrame()
        self.panel.setObjectName("CaptureDialog")
        self.panel.setFixedWidth(PANEL_WIDTH)
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(26, 24, 26, 22)
        panel_layout.setSpacing(0)

        # Eyebrow with its copper dot
        eyebrow_row = QHBoxLayout()
        eyebrow_row.setContentsMargins(0, 0, 0, 0)
        eyebrow_row.setSpacing(7)
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background: {palette.copper};")
        eyebrow_row.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        title = QLabel("CAPTURE")
        title.setObjectName("BoxLabel")
        title_font = title.font()
        title_font.setLetterSpacing(title_font.SpacingType.PercentageSpacing, 114)
        title.setFont(title_font)
        eyebrow_row.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)
        panel_layout.addLayout(eyebrow_row)
        panel_layout.addSpacing(14)

        self.kind_toggle = KindToggle()
        self.kind_toggle.set_palette(palette)
        panel_layout.addWidget(self.kind_toggle)
        panel_layout.addSpacing(14)

        panel_layout.addWidget(_field_label("What is it?"))
        panel_layout.addSpacing(6)
        self.text_field = QLineEdit()
        self.text_field.setObjectName("CaptureField")
        self.text_field.setPlaceholderText("One line is enough…")
        self.text_field.textChanged.connect(self._sync_enabled)
        panel_layout.addWidget(self.text_field)
        panel_layout.addSpacing(14)

        panel_layout.addWidget(_field_label("Which app?"))
        panel_layout.addSpacing(6)
        self.app_picker = QComboBox()
        self.app_picker.setObjectName("CapturePicker")
        panel_layout.addWidget(self.app_picker)

        self.no_apps = QLabel(NO_APPS_TEXT)
        self.no_apps.setObjectName("CaptureNoApps")
        self.no_apps.setWordWrap(True)
        self.no_apps.setVisible(False)
        panel_layout.addSpacing(8)
        panel_layout.addWidget(self.no_apps)

        panel_layout.addSpacing(18)
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(12)
        actions.addStretch(1)
        cancel = TextButton("Cancel", "GhostButton")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        self.keep_button = TextButton("Keep it  ↲", "CopperButton")
        self.keep_button.clicked.connect(self._keep)
        actions.addWidget(self.keep_button)
        panel_layout.addLayout(actions)

        centring.addWidget(self.panel)
        centring.addStretch(1)
        outer.addLayout(centring)
        outer.addStretch(1)

        self._load_apps(last_app_id)

    # ---------- loading ----------

    def _load_apps(self, last_app_id: int | None) -> None:
        """Apps in alphabetical order, with the last one captured to preselected."""
        apps = self.store.list_apps()
        self.app_picker.clear()
        for app in apps:
            self.app_picker.addItem(app.name, app.id)

        has_apps = bool(apps)
        self.app_picker.setEnabled(has_apps)
        self.app_picker.setVisible(has_apps)
        self.no_apps.setVisible(not has_apps)

        if has_apps and last_app_id is not None:
            index = self.app_picker.findData(last_app_id)
            if index >= 0:
                self.app_picker.setCurrentIndex(index)

        self._sync_enabled()

    def _sync_enabled(self) -> None:
        ready = bool(self.text_field.text().strip()) and self.app_picker.count() > 0
        self.keep_button.setEnabled(ready)

    @property
    def selected_app_id(self) -> int | None:
        if self.app_picker.count() == 0:
            return None
        return self.app_picker.currentData()

    # ---------- keeping ----------

    def _keep(self) -> None:
        text = self.text_field.text().strip()
        app_id = self.selected_app_id
        if not text or app_id is None:
            return
        self.store.add_sheet_item(app_id, self.kind_toggle.kind, text)
        self.captured.emit(int(app_id), self.kind_toggle.kind)
        self.accept()

    # ---------- appearance and interaction ----------

    def showEvent(self, event: QEvent) -> None:
        """Cover the window, then put the cursor where the typing goes."""
        parent = self.parentWidget()
        if parent is not None:
            top_left = parent.mapToGlobal(parent.rect().topLeft())
            self.setGeometry(
                top_left.x(), top_left.y(), parent.width(), parent.height()
            )
        super().showEvent(event)
        # Typing must start the instant the dialog appears. Focus is claimed
        # explicitly, with a reason, or it lands on the first segment button.
        self.activateWindow()
        self.text_field.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def paintEvent(self, _event: object) -> None:
        """The scrim: the window dimmed behind the panel."""
        painter = QPainter(self)
        colour = QColor(self.tokens.surface_deep)
        colour.setAlpha(184)
        painter.fillRect(self.rect(), colour)
        painter.end()

    def mousePressEvent(self, event: QEvent) -> None:
        """A click outside the panel gives up on the capture."""
        if not self.panel.geometry().contains(event.position().toPoint()):
            self.reject()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Enter keeps it from anywhere in the dialog.
            self._keep()
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and not isinstance(
            self.focusWidget(), (QLineEdit, QComboBox)
        ):
            self.kind_toggle.toggle()
            event.accept()
            return
        super().keyPressEvent(event)


def _field_label(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("FieldLabel")
    font = label.font()
    font.setLetterSpacing(font.SpacingType.PercentageSpacing, 114)
    label.setFont(font)
    return label
