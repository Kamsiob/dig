"""Shared scaffolding for the five screens."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from dig.storage import Store
from dig.theme.tokens import Palette
from dig.ui.widgets import eyebrow

CONTENT_MARGINS = (52, 44, 52, 64)


class Screen(QWidget):
    """One view in the main area.

    Screens rebuild their contents in `refresh()` whenever they are shown, so
    what is on screen always reflects what is in the store.
    """

    title = ""
    """Nav key this screen answers to."""

    def __init__(self, store: Store, palette: Palette, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store
        self.tokens = palette

    def refresh(self) -> None:
        """Rebuild from the store. Called every time the screen is shown."""

    def set_palette(self, palette: Palette) -> None:
        """Adopt a new palette. Custom-painted children repaint themselves."""
        self.tokens = palette

    def on_shown(self) -> None:
        """Called after the screen becomes visible."""
        self.refresh()


class ScrollableScreen(Screen):
    """A screen whose content scrolls when the window is short."""

    def __init__(self, store: Store, palette: Palette, parent: QWidget | None = None):
        super().__init__(store, palette, parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(self.scroll)

        self.content = QWidget()
        self.content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.column = QVBoxLayout(self.content)
        left, top, right, bottom = CONTENT_MARGINS
        self.column.setContentsMargins(left, top, right, bottom)
        self.column.setSpacing(0)
        self.scroll.setWidget(self.content)


class PlaceholderScreen(ScrollableScreen):
    """A screen that is not built yet. Replaced as each phase lands."""

    def __init__(
        self,
        store: Store,
        palette: Palette,
        heading: str,
        note: str,
        parent: QWidget | None = None,
    ):
        super().__init__(store, palette, parent)
        self.column.addWidget(eyebrow(heading, section=True))
        self.column.addSpacing(12)
        message = QLabel(note)
        message.setObjectName("Placeholder")
        message.setWordWrap(True)
        self.column.addWidget(message)
        self.column.addStretch(1)
