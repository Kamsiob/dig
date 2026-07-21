"""Home: jot an idea, see the last three, and dig an old one back up."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from dig import timefmt
from dig.screens.base import ScrollableScreen
from dig.storage import RECENT_COUNT, Idea, Store
from dig.theme import prefers_reduced_motion
from dig.theme.tokens import Palette
from dig.ui.ledger import LedgerRow
from dig.ui.unearthed import UnearthedBlock
from dig.ui.widgets import TextButton, eyebrow

HIGHLIGHT_MS = 1500
JOT_PLACEHOLDER = "Jot the new idea before it goes…"


class JotBox(QFrame):
    """Where a new idea lands. Focus lives here whenever Home is open."""

    kept = Signal(str)

    def __init__(self, palette: Palette, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("JotBox")
        column = QVBoxLayout(self)
        column.setContentsMargins(20, 18, 20, 14)
        column.setSpacing(8)

        self.field = _JotField()
        self.field.setObjectName("JotField")
        self.field.setPlaceholderText(JOT_PLACEHOLDER)
        self.field.setFixedHeight(56)
        self.field.keep_requested.connect(self._keep)
        column.addWidget(self.field)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        hint = QLabel("Shift+Enter for a new line")
        hint.setObjectName("JotHint")
        row.addWidget(hint, 1, Qt.AlignmentFlag.AlignVCenter)

        self.keep_button = TextButton("Keep it  ↲", "PrimaryButton")
        self.keep_button.clicked.connect(self._keep)
        row.addWidget(self.keep_button, 0, Qt.AlignmentFlag.AlignVCenter)

        column.addLayout(row)

    def _keep(self) -> None:
        """Enter and the button do exactly the same thing."""
        text = self.field.toPlainText()
        if not text.strip():
            # Nothing typed. Say nothing, do nothing.
            return
        self.kept.emit(text)
        self.field.clear()
        self.field.setFocus()

    def take_focus(self) -> None:
        self.field.setFocus()


class _JotField(QTextEdit):
    """Enter keeps the idea. Shift+Enter is a new line."""

    keep_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
                return
            self.keep_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class CapturePanel(QWidget):
    """The dashed copper panel that opens the capture dialog."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("CapturePanel")
        self.setFixedWidth(172)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # A plain QWidget draws no stylesheet background or border without
        # this, which would lose the dashed copper edge entirely.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        column = QVBoxLayout(self)
        column.setContentsMargins(12, 14, 12, 14)
        column.setSpacing(4)
        column.addStretch(1)

        plus = QLabel("+")
        plus.setObjectName("CapturePlus")
        plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(plus)

        label = QLabel("Capture")
        label.setObjectName("CaptureLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(label)

        sub = QLabel("feature or bug")
        sub.setObjectName("CaptureSub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(sub)

        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(0, 6, 0, 0)
        badge = QLabel("Ctrl K")
        badge.setObjectName("CaptureKey")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_row.addStretch(1)
        badge_row.addWidget(badge)
        badge_row.addStretch(1)
        column.addLayout(badge_row)
        column.addStretch(1)

    def mouseReleaseEvent(self, event: object) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class HomeScreen(ScrollableScreen):
    """The screen Dig opens on."""

    idea_opened = Signal(int)
    promote_requested = Signal(int)
    all_ideas_requested = Signal()
    capture_requested = Signal()

    def __init__(self, store: Store, palette: Palette, parent: QWidget | None = None):
        super().__init__(store, palette, parent)
        self._shown_unearthed_id: int | None = None
        self._highlight_id: int | None = None
        self._animation: QVariantAnimation | None = None
        self._rows: list[LedgerRow] = []

        self.today = QLabel("")
        self.today.setObjectName("Eyebrow")
        today_font = self.today.font()
        today_font.setLetterSpacing(today_font.SpacingType.PercentageSpacing, 115)
        self.today.setFont(today_font)
        self.column.addWidget(self.today)
        self.column.addSpacing(10)

        heading = QHBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(0)
        lead = QLabel("What did you just ")
        lead.setObjectName("H1")
        tail = QLabel("think of?")
        tail.setObjectName("H1Accent")
        heading.addWidget(lead, 0, Qt.AlignmentFlag.AlignBaseline)
        heading.addWidget(tail, 0, Qt.AlignmentFlag.AlignBaseline)
        heading.addStretch(1)
        self.column.addLayout(heading)
        self.column.addSpacing(26)

        # Capture row: the jot well beside the dashed capture panel.
        capture_row = QHBoxLayout()
        capture_row.setContentsMargins(0, 0, 0, 0)
        capture_row.setSpacing(14)

        jot_column = QVBoxLayout()
        jot_column.setContentsMargins(0, 0, 0, 0)
        jot_column.setSpacing(7)
        jot_column.addWidget(_box_label("New app idea", palette.accent))
        self.jot = JotBox(palette)
        self.jot.kept.connect(self._keep_idea)
        jot_column.addWidget(self.jot)
        capture_row.addLayout(jot_column, 1)

        panel_column = QVBoxLayout()
        panel_column.setContentsMargins(0, 0, 0, 0)
        panel_column.setSpacing(7)
        panel_column.addWidget(_box_label("Existing app", palette.copper))
        self.capture_panel = CapturePanel()
        self.capture_panel.clicked.connect(self.capture_requested)
        panel_column.addWidget(self.capture_panel, 1)
        capture_row.addLayout(panel_column, 0)

        self.column.addLayout(capture_row)

        # Recent
        self.column.addSpacing(40)
        recent_head = QHBoxLayout()
        recent_head.setContentsMargins(0, 0, 0, 0)
        recent_head.setSpacing(12)
        recent_head.addWidget(eyebrow("Recent", section=True))
        recent_head.addStretch(1)
        all_ideas = TextButton("All ideas →", "LinkAccent")
        all_ideas.clicked.connect(self.all_ideas_requested)
        recent_head.addWidget(all_ideas)
        self.column.addLayout(recent_head)
        self.column.addSpacing(4)

        self.recent_holder = QWidget()
        self.recent_layout = QVBoxLayout(self.recent_holder)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_layout.setSpacing(0)
        self.column.addWidget(self.recent_holder)

        self.recent_empty = QLabel("Nothing buried yet. Jot the first one above.")
        self.recent_empty.setObjectName("EmptyState")
        self.column.addWidget(self.recent_empty)

        # Unearthed
        self.column.addSpacing(44)
        self.unearthed = UnearthedBlock(palette)
        self.unearthed.open_requested.connect(self._open_unearthed)
        self.unearthed.dig_again_requested.connect(self.dig_again)
        self.column.addWidget(self.unearthed)

        self.column.addStretch(1)

    # ---------- building ----------

    def refresh(self) -> None:
        self.today.setText(timefmt.today_eyebrow().upper())
        self._rebuild_recent()
        self._draw_unearthed(keep_current=True)

    def _rebuild_recent(self) -> None:
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows = []

        ideas = self.store.recent_ideas(RECENT_COUNT)
        self.recent_empty.setVisible(not ideas)
        self.recent_holder.setVisible(bool(ideas))

        for idea in ideas:
            row = LedgerRow(idea, self.tokens)
            row.opened.connect(self.idea_opened)
            row.promote_requested.connect(self.promote_requested)
            self.recent_layout.addWidget(row)
            self._rows.append(row)

        if self._highlight_id is not None:
            self._flash(self._highlight_id)
            self._highlight_id = None

    def _draw_unearthed(self, keep_current: bool = False) -> None:
        """Pick a specimen. Coming back to Home draws a fresh one."""
        if keep_current and self._shown_unearthed_id is not None:
            still_there = self.store.get_idea(self._shown_unearthed_id)
            pool_ids = {i.id for i in self.store.unearth_candidates()}
            if still_there is not None and still_there.id in pool_ids:
                self.unearthed.show_idea(still_there)
                return

        idea = self.store.unearth()
        if idea is None:
            self._shown_unearthed_id = None
            self.unearthed.show_empty()
            return
        self._shown_unearthed_id = idea.id
        self.unearthed.show_idea(idea)

    def dig_again(self) -> None:
        """Redraw, never returning the idea already on display."""
        idea = self.store.unearth(exclude_id=self._shown_unearthed_id)
        if idea is None:
            # A pool of one. Nothing to swap to, so nothing happens.
            return
        self._shown_unearthed_id = idea.id
        self.unearthed.show_idea(idea)

    def on_shown(self) -> None:
        """Home always opens with the cursor already in the jot field."""
        self.today.setText(timefmt.today_eyebrow().upper())
        self._rebuild_recent()
        self._draw_unearthed(keep_current=False)
        self.jot.take_focus()

    # ---------- actions ----------

    def _keep_idea(self, raw: str) -> None:
        idea = self.store.create_idea(raw)
        if idea is None:
            return
        self._highlight_id = idea.id
        self._rebuild_recent()

    def _open_unearthed(self, idea_id: int) -> None:
        """Opening an unearthed idea stamps that it was looked at."""
        self.store.mark_idea_opened(idea_id)
        self.idea_opened.emit(idea_id)

    # ---------- the highlight ----------

    def _flash(self, idea_id: int) -> None:
        """A brief gold wash so a kept idea is visibly kept."""
        row = next((r for r in self._rows if r.idea.id == idea_id), None)
        if row is None:
            return
        if prefers_reduced_motion():
            return

        start = QColor(self.tokens.accent)
        start.setAlpha(60)
        end = QColor(self.tokens.accent)
        end.setAlpha(0)

        animation = QVariantAnimation(self)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.setDuration(HIGHLIGHT_MS)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        def paint(colour: QColor) -> None:
            if row is None or not row.isVisible():
                return
            row.setStyleSheet(
                f"#LedgerRow {{ background: rgba({colour.red()}, {colour.green()}, "
                f"{colour.blue()}, {colour.alphaF():.3f}); }}"
            )

        animation.valueChanged.connect(paint)
        animation.finished.connect(lambda: row.setStyleSheet(""))
        animation.start()
        self._animation = animation

    def set_palette(self, palette: Palette) -> None:
        super().set_palette(palette)
        self.unearthed.set_palette(palette)
        for row in self._rows:
            row.set_palette(palette)


def _box_label(text: str, dot_colour: str) -> QWidget:
    """A small square colour dot beside a mono uppercase label."""
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(7)

    dot = QLabel()
    dot.setFixedSize(8, 8)
    dot.setStyleSheet(f"background: {dot_colour};")
    row.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

    label = QLabel(text.upper())
    label.setObjectName("BoxLabel")
    font = label.font()
    font.setLetterSpacing(font.SpacingType.PercentageSpacing, 114)
    label.setFont(font)
    row.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)
    row.addStretch(1)
    return holder
