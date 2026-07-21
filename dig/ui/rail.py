"""The left rail: wordmark, navigation, appearance, and the local-only footer."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from dig import __version__
from dig.theme import MODE_LABELS, MODES
from dig.theme.tokens import Palette
from dig.ui.widgets import StatusLamp, TextButton, Wordmark, WordmarkRule

RAIL_WIDTH = 216

SCREENS = (
    ("home", "Home", "1"),
    ("ideas", "Ideas", "2"),
    ("apps", "Apps", "3"),
    ("export", "Export", "4"),
    ("settings", "Settings", "5"),
)


class NavItem(QPushButton):
    """One navigation row: label on the left, mono number hint on the right."""

    def __init__(self, key: str, label: str, hint: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.key = key
        self.setObjectName("NavItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(False)
        self.setProperty("active", False)

        row = QHBoxLayout(self)
        row.setContentsMargins(21, 9, 24, 9)
        row.setSpacing(8)

        self.label = QLabel(label)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.hint = QLabel(hint)
        self.hint.setObjectName("NavHint")
        self.hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        row.addWidget(self.label)
        row.addStretch(1)
        row.addWidget(self.hint, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", active)
        # Qt only restyles on a property change when told to.
        self.style().unpolish(self)
        self.style().polish(self)


class Segmented(QFrame):
    """The Light / Dark / System control. Used in the rail and in Settings."""

    picked = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Segmented")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._buttons: dict[str, QPushButton] = {}
        for index, mode in enumerate(MODES):
            button = QPushButton(MODE_LABELS[mode])
            button.setObjectName("Segment")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("active", False)
            button.clicked.connect(lambda _checked=False, m=mode: self.picked.emit(m))
            if index:
                divider = QFrame()
                divider.setObjectName("SegmentDivider")
                divider.setFixedWidth(1)
                row.addWidget(divider)
                self._dividers = getattr(self, "_dividers", [])
                self._dividers.append(divider)
            row.addWidget(button, 1)
            self._buttons[mode] = button

    def set_mode(self, mode: str) -> None:
        for key, button in self._buttons.items():
            button.setProperty("active", key == mode)
            button.style().unpolish(button)
            button.style().polish(button)

    def set_palette(self, palette: Palette) -> None:
        for divider in getattr(self, "_dividers", []):
            divider.setStyleSheet(f"background: {palette.seam};")


class Rail(QFrame):
    """The whole left column."""

    navigated = Signal(str)
    appearance_picked = Signal(str)
    about_requested = Signal()

    def __init__(self, palette: Palette, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Rail")
        self.setFixedWidth(RAIL_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 30, 0, 24)
        column.setSpacing(0)

        # Wordmark and its two-tone rule
        mark_holder = QWidget()
        mark_layout = QVBoxLayout(mark_holder)
        mark_layout.setContentsMargins(24, 0, 24, 0)
        mark_layout.setSpacing(0)
        self.wordmark = Wordmark(palette)
        mark_layout.addWidget(self.wordmark)
        self.rule = WordmarkRule(palette)
        mark_layout.addSpacing(6)
        mark_layout.addWidget(self.rule)
        column.addWidget(mark_holder)

        byline = QLabel("BY KAMSIOB")
        byline.setObjectName("Byline")
        byline_font = byline.font()
        byline_font.setLetterSpacing(byline_font.SpacingType.PercentageSpacing, 115)
        byline.setFont(byline_font)
        byline_holder = QWidget()
        byline_layout = QVBoxLayout(byline_holder)
        byline_layout.setContentsMargins(24, 4, 24, 28)
        byline_layout.setSpacing(0)
        byline_layout.addWidget(byline)
        column.addWidget(byline_holder)

        # Navigation
        self.nav_items: dict[str, NavItem] = {}
        for key, label, hint in SCREENS:
            item = NavItem(key, label, hint)
            item.clicked.connect(lambda _checked=False, k=key: self.navigated.emit(k))
            column.addWidget(item)
            self.nav_items[key] = item

        # Appearance
        appearance = QWidget()
        appearance_layout = QVBoxLayout(appearance)
        appearance_layout.setContentsMargins(24, 26, 24, 0)
        appearance_layout.setSpacing(8)
        appearance_label = QLabel("APPEARANCE")
        appearance_label.setObjectName("SegmentLabel")
        label_font = appearance_label.font()
        label_font.setLetterSpacing(label_font.SpacingType.PercentageSpacing, 115)
        appearance_label.setFont(label_font)
        appearance_layout.addWidget(appearance_label)
        self.segmented = Segmented()
        self.segmented.picked.connect(self.appearance_picked)
        appearance_layout.addWidget(self.segmented)
        column.addWidget(appearance)

        column.addStretch(1)

        # Footer: the promise, then About and the version
        foot = QWidget()
        foot.setObjectName("RailFoot")
        foot_layout = QVBoxLayout(foot)
        foot_layout.setContentsMargins(20, 0, 16, 0)
        foot_layout.setSpacing(4)

        promise_row = QWidget()
        promise_layout = QHBoxLayout(promise_row)
        promise_layout.setContentsMargins(0, 0, 0, 0)
        promise_layout.setSpacing(6)
        self.lamp = StatusLamp(palette)
        promise_layout.addWidget(self.lamp, 0, Qt.AlignmentFlag.AlignTop)
        promise = QLabel("local only · nothing leaves")
        promise.setObjectName("RailFoot")
        # The rail is a fixed 216px; the promise wraps rather than being cut off.
        promise.setWordWrap(True)
        promise_layout.addWidget(promise, 1)
        foot_layout.addWidget(promise_row)

        about_row = QWidget()
        about_layout = QHBoxLayout(about_row)
        about_layout.setContentsMargins(0, 0, 0, 0)
        about_layout.setSpacing(6)
        self.about = TextButton("About Dig", "AboutTrigger")
        about_font = self.about.font()
        about_font.setUnderline(True)
        self.about.setFont(about_font)
        self.about.clicked.connect(self.about_requested)
        about_layout.addWidget(self.about)
        version = QLabel(f"· v{__version__}")
        version.setObjectName("RailFoot")
        about_layout.addWidget(version)
        about_layout.addStretch(1)
        foot_layout.addWidget(about_row)

        column.addWidget(foot)

        self.set_palette(palette)

    def set_active(self, key: str) -> None:
        for nav_key, item in self.nav_items.items():
            item.set_active(nav_key == key)

    def set_mode(self, mode: str) -> None:
        self.segmented.set_mode(mode)

    def set_palette(self, palette: Palette) -> None:
        self.wordmark.set_palette(palette)
        self.rule.set_palette(palette)
        self.lamp.set_palette(palette)
        self.segmented.set_palette(palette)
