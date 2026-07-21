"""The main window: rail on the left, one screen at a time on the right."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from dig.screens.base import PlaceholderScreen, Screen
from dig.storage import Store
from dig.theme import APPEARANCE_KEY, ThemeManager
from dig.ui.backdrop import GrainOverlay, MapBackdrop
from dig.ui.rail import Rail, SCREENS

MIN_WIDTH = 980
MIN_HEIGHT = 640

GEOMETRY_KEY = "window_geometry"
STATE_KEY = "window_state"

# Screens that show the treasure map behind their content. Home only.
MAP_SCREENS = {"home"}


class NoticeBar(QWidget):
    """A plain line across the top of the content when Dig has something to say.

    States what happened and what it did about it. It never apologises.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("NoticeBar")
        row = QHBoxLayout(self)
        row.setContentsMargins(52, 14, 20, 14)
        row.setSpacing(16)

        self.message = QLabel("")
        self.message.setObjectName("NoticeText")
        self.message.setWordWrap(True)
        row.addWidget(self.message, 1)

        self.dismiss = QPushButton("Dismiss")
        self.dismiss.setObjectName("GhostButton")
        self.dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dismiss.clicked.connect(self.hide)
        row.addWidget(self.dismiss, 0, Qt.AlignmentFlag.AlignTop)

    def say(self, text: str) -> None:
        self.message.setText(text)
        self.show()


class MainWindow(QMainWindow):
    """Everything the user sees."""

    def __init__(self, store: Store, theme: ThemeManager):
        super().__init__()
        self.store = store
        self.theme = theme
        self._current = "home"

        self.setWindowTitle("Dig")
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        row = QHBoxLayout(root)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.rail = Rail(theme.palette)
        self.rail.navigated.connect(self.go_to)
        self.rail.appearance_picked.connect(self.set_appearance)
        self.rail.about_requested.connect(self.show_about)
        row.addWidget(self.rail)

        # The main area holds the map backdrop behind a stack of screens.
        self.main_area = QWidget()
        self.main_area.setObjectName("MainArea")
        row.addWidget(self.main_area, 1)

        self.map_backdrop = MapBackdrop(theme.palette, self.main_area)
        self.map_backdrop.lower()

        area_layout = QVBoxLayout(self.main_area)
        area_layout.setContentsMargins(0, 0, 0, 0)
        area_layout.setSpacing(0)

        self.notice = NoticeBar()
        self.notice.hide()
        area_layout.addWidget(self.notice)

        self.stack = QStackedWidget()
        self.stack.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        area_layout.addWidget(self.stack)

        self.screens: dict[str, Screen] = {}
        self._build_screens()

        # Paper grain sits over everything and never takes a click.
        self.grain = GrainOverlay(root)
        self.grain.raise_()

        self.theme.changed.connect(self._on_theme_changed)

        self._restore_geometry()
        self.rail.set_mode(self.theme.mode)
        self.go_to("home")

    # ---------- screens ----------

    def _build_screens(self) -> None:
        """Each phase replaces one of these placeholders with the real screen."""
        blurbs = {
            "home": "Jot capture, Recent, and Unearthed arrive with the Home phase.",
            "ideas": "The full idea ledger with search arrives with the Ideas phase.",
            "apps": "The app registry and its sheets arrive with the Apps phase.",
            "export": "The PDF portfolio arrives with the Export phase.",
            "settings": "Appearance and the data folder arrive with the Settings phase.",
        }
        for key, label, _hint in SCREENS:
            screen = PlaceholderScreen(
                self.store, self.theme.palette, label, blurbs[key]
            )
            self.screens[key] = screen
            self.stack.addWidget(screen)

    def replace_screen(self, key: str, screen: Screen) -> None:
        """Swap a placeholder for the real thing."""
        old = self.screens.get(key)
        if old is not None:
            index = self.stack.indexOf(old)
            self.stack.removeWidget(old)
            old.deleteLater()
        else:
            index = self.stack.count()
        self.stack.insertWidget(index, screen)
        self.screens[key] = screen
        if self._current == key:
            self.stack.setCurrentWidget(screen)

    def go_to(self, key: str) -> None:
        """Show a screen and mark its nav row active."""
        screen = self.screens.get(key)
        if screen is None:
            return
        self._current = key
        self.stack.setCurrentWidget(screen)
        self.rail.set_active(key)
        self.map_backdrop.setVisible(key in MAP_SCREENS)
        screen.on_shown()

    @property
    def current_screen_key(self) -> str:
        return self._current

    # ---------- appearance ----------

    def set_appearance(self, mode: str) -> None:
        """Change the appearance and remember the choice."""
        self.theme.set_mode(mode)
        self.store.set_setting(APPEARANCE_KEY, mode)

    def _on_theme_changed(self) -> None:
        palette = self.theme.palette
        self.rail.set_palette(palette)
        self.rail.set_mode(self.theme.mode)
        self.map_backdrop.set_palette(palette)
        for screen in self.screens.values():
            screen.set_palette(palette)
        self.update()

    def show_notice(self, text: str) -> None:
        """Tell the user something plainly, at the top of the content."""
        self.notice.say(text)

    def show_about(self) -> None:
        """The About dialog arrives with the Settings phase."""

    # ---------- geometry ----------

    def _restore_geometry(self) -> None:
        """Come back the size and place the window was left."""
        saved = self.store.get_setting(GEOMETRY_KEY, "")
        restored = False
        if saved:
            try:
                from PySide6.QtCore import QByteArray

                restored = self.restoreGeometry(
                    QByteArray.fromBase64(saved.encode("ascii"))
                )
            except (ValueError, TypeError):
                restored = False
        if not restored:
            self.resize(1080, 720)

    def _save_geometry(self) -> None:
        try:
            raw = bytes(self.saveGeometry().toBase64()).decode("ascii")
            self.store.set_setting(GEOMETRY_KEY, raw)
        except Exception:
            # Never let a failed geometry save stop the window from closing.
            pass

    def closeEvent(self, event: QEvent) -> None:
        self._save_geometry()
        super().closeEvent(event)

    def resizeEvent(self, event: QEvent) -> None:
        super().resizeEvent(event)
        central = self.centralWidget()
        if central is not None:
            self.grain.setGeometry(central.rect())
            self.grain.raise_()
        self.map_backdrop.setGeometry(self.main_area.rect())
        self.map_backdrop.lower()

    # ---------- keyboard ----------

    @staticmethod
    def _is_typing(widget: QWidget | None) -> bool:
        """True when the focus is in something that takes text."""
        return isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Number keys switch screens, but never while typing."""
        key = event.key()
        if (
            Qt.Key.Key_1 <= key <= Qt.Key.Key_5
            and not event.modifiers()
            and not self._is_typing(self.focusWidget())
        ):
            index = key - Qt.Key.Key_1
            self.go_to(SCREENS[index][0])
            event.accept()
            return
        super().keyPressEvent(event)
