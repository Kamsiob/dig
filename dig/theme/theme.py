"""Which palette is in force, and telling the interface when it changes.

Appearance is Light, Dark, or System. System follows the desktop live: when the
OS switches scheme, Dig switches with it without a restart.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QGuiApplication

from dig.theme import qss
from dig.theme.tokens import DARK, LIGHT, Palette

LIGHT_MODE = "light"
DARK_MODE = "dark"
SYSTEM_MODE = "system"
MODES = (LIGHT_MODE, DARK_MODE, SYSTEM_MODE)

MODE_LABELS = {LIGHT_MODE: "Light", DARK_MODE: "Dark", SYSTEM_MODE: "System"}

APPEARANCE_KEY = "appearance"


class ThemeManager(QObject):
    """Resolves the appearance setting into a palette and a stylesheet."""

    changed = Signal()
    """The palette in force is now different. Repaint anything custom-drawn."""

    def __init__(self, mode: str = SYSTEM_MODE, parent: QObject | None = None):
        super().__init__(parent)
        self._mode = mode if mode in MODES else SYSTEM_MODE
        hints = QGuiApplication.styleHints()
        if hints is not None:
            # Qt 6.5 and later report the desktop's light/dark preference and
            # signal when the user changes it mid-session.
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    # ---------- state ----------

    @property
    def mode(self) -> str:
        """The setting as chosen: light, dark, or system."""
        return self._mode

    @property
    def is_dark(self) -> bool:
        """What the setting resolves to right now."""
        if self._mode == DARK_MODE:
            return True
        if self._mode == LIGHT_MODE:
            return False
        return self.system_is_dark()

    @property
    def palette(self) -> Palette:
        return DARK if self.is_dark else LIGHT

    @staticmethod
    def system_is_dark() -> bool:
        """The desktop's own light/dark preference."""
        hints = QGuiApplication.styleHints()
        if hints is None:
            return False
        return hints.colorScheme() == Qt.ColorScheme.Dark

    # ---------- changing ----------

    def set_mode(self, mode: str) -> None:
        """Choose an appearance. Re-applies only when something really changed."""
        if mode not in MODES:
            return
        self._mode = mode
        self.apply()
        # Emitted even when the resolved palette is unchanged (light to system
        # on a light desktop): the segmented controls still need to restate
        # which segment is the chosen one.
        self.changed.emit()

    def _on_system_scheme_changed(self, _scheme: object = None) -> None:
        """The desktop switched scheme. Only System mode follows it."""
        if self._mode != SYSTEM_MODE:
            return
        self.apply()
        self.changed.emit()

    def apply(self) -> None:
        """Push the current palette onto the application as a stylesheet."""
        app = QGuiApplication.instance()
        if app is None:
            return
        sheet = qss.build(self.palette)
        # QGuiApplication has no setStyleSheet; QApplication does.
        setter = getattr(app, "setStyleSheet", None)
        if setter is not None:
            setter(sheet)
