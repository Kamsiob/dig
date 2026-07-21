"""The Export screen: choose what goes in the portfolio, then write the PDF."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from dig import timefmt
from dig.export import AppPage, IdeaLine, Portfolio, write_portfolio
from dig.screens.base import ScrollableScreen
from dig.storage import FEATURE, Store
from dig.theme.tokens import Palette
from dig.ui.attachments import open_with_the_system
from dig.ui.widgets import TextButton, eyebrow
from dig.ui.work import run_off_thread

DEFAULT_NAME = "Dig Portfolio.pdf"


def default_destination() -> Path:
    """The Desktop if there is one, otherwise the home folder."""
    desktop = Path.home() / "Desktop"
    folder = desktop if desktop.is_dir() else Path.home()
    return folder / DEFAULT_NAME


class ExportScreen(ScrollableScreen):
    """Pick the apps and ideas, pick a file, write it."""

    exported = Signal(str)

    def __init__(self, store: Store, palette: Palette, parent: QWidget | None = None):
        super().__init__(store, palette, parent)
        self._app_boxes: list[tuple[QCheckBox, int]] = []
        self._idea_boxes: list[tuple[QCheckBox, int]] = []
        self._busy = False

        self.column.addWidget(eyebrow("Export", section=True))
        self.column.addSpacing(8)

        intro = QLabel(
            "A portfolio, not a report. Bug sheets stay here; "
            "what goes out is what the apps are and what they look like."
        )
        intro.setObjectName("BodyText")
        intro.setWordWrap(True)
        self.column.addWidget(intro)
        self.column.addSpacing(28)

        # Apps
        apps_head = QHBoxLayout()
        apps_head.setContentsMargins(0, 0, 0, 0)
        apps_head.setSpacing(14)
        apps_head.addWidget(eyebrow("Apps", section=True))
        apps_head.addStretch(1)
        self.all_apps = QCheckBox("All")
        self.all_apps.setObjectName("ShowPromoted")
        self.all_apps.setTristate(True)
        self.all_apps.clicked.connect(self._toggle_all_apps)
        apps_head.addWidget(self.all_apps)
        self.column.addLayout(apps_head)
        self.column.addSpacing(6)

        self.apps_holder = QWidget()
        self.apps_layout = QVBoxLayout(self.apps_holder)
        self.apps_layout.setContentsMargins(0, 0, 0, 0)
        self.apps_layout.setSpacing(2)
        self.column.addWidget(self.apps_holder)

        self.apps_empty = QLabel("No apps yet.")
        self.apps_empty.setObjectName("SheetEmpty")
        self.column.addWidget(self.apps_empty)
        self.column.addSpacing(28)

        # Ideas
        ideas_head = QHBoxLayout()
        ideas_head.setContentsMargins(0, 0, 0, 0)
        ideas_head.setSpacing(14)
        ideas_head.addWidget(eyebrow("Ideas", section=True))
        ideas_head.addStretch(1)
        self.all_ideas = QCheckBox("All")
        self.all_ideas.setObjectName("ShowPromoted")
        self.all_ideas.setTristate(True)
        self.all_ideas.clicked.connect(self._toggle_all_ideas)
        ideas_head.addWidget(self.all_ideas)
        self.column.addLayout(ideas_head)
        self.column.addSpacing(6)

        self.ideas_holder = QWidget()
        self.ideas_layout = QVBoxLayout(self.ideas_holder)
        self.ideas_layout.setContentsMargins(0, 0, 0, 0)
        self.ideas_layout.setSpacing(2)
        self.column.addWidget(self.ideas_holder)

        self.ideas_empty = QLabel("Nothing buried yet.")
        self.ideas_empty.setObjectName("SheetEmpty")
        self.column.addWidget(self.ideas_empty)
        self.column.addSpacing(32)

        # Where it goes
        self.column.addWidget(_field_label("Save to"))
        self.column.addSpacing(6)
        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(12)
        self.path_field = QLineEdit(str(default_destination()))
        self.path_field.setObjectName("FormField")
        path_row.addWidget(self.path_field, 1)
        choose = TextButton("Choose…", "GhostButton")
        choose.clicked.connect(self._choose_destination)
        path_row.addWidget(choose)
        self.column.addLayout(path_row)
        self.column.addSpacing(24)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(16)
        self.export_button = TextButton("Export PDF", "PrimaryButton")
        self.export_button.clicked.connect(self._export)
        actions.addWidget(self.export_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.result = QLabel("")
        self.result.setObjectName("EditorMeta")
        self.result.setVisible(False)
        actions.addWidget(self.result, 1, Qt.AlignmentFlag.AlignVCenter)

        self.open_it = TextButton("Open it", "LinkAccent")
        self.open_it.clicked.connect(self._open_result)
        self.open_it.setVisible(False)
        actions.addWidget(self.open_it, 0, Qt.AlignmentFlag.AlignVCenter)

        actions.addStretch(1)
        self.column.addLayout(actions)
        self.column.addStretch(1)

        self._written: Path | None = None

    # ---------- building ----------

    def refresh(self) -> None:
        """Rebuild the two lists, keeping the defaults the design asks for."""
        for box, _ident in self._app_boxes + self._idea_boxes:
            box.setParent(None)
            box.deleteLater()
        self._app_boxes = []
        self._idea_boxes = []

        apps = self.store.list_apps()
        for app in apps:
            box = QCheckBox(app.name)
            box.setObjectName("ShowPromoted")
            # Shipped apps are what a portfolio is for, so they start ticked.
            box.setChecked(app.shipped)
            box.toggled.connect(self._sync)
            self.apps_layout.addWidget(box)
            self._app_boxes.append((box, app.id))
        self.apps_empty.setVisible(not apps)
        self.apps_holder.setVisible(bool(apps))

        ideas = self.store.list_ideas()
        for idea in ideas:
            box = QCheckBox(idea.title)
            box.setObjectName("ShowPromoted")
            box.setChecked(False)  # ideas are opt-in
            box.toggled.connect(self._sync)
            self.ideas_layout.addWidget(box)
            self._idea_boxes.append((box, idea.id))
        self.ideas_empty.setVisible(not ideas)
        self.ideas_holder.setVisible(bool(ideas))

        self._sync()

    # ---------- selection ----------

    def _toggle_all_apps(self) -> None:
        wanted = not all(box.isChecked() for box, _ in self._app_boxes)
        for box, _ident in self._app_boxes:
            box.setChecked(wanted)
        self._sync()

    def _toggle_all_ideas(self) -> None:
        wanted = not all(box.isChecked() for box, _ in self._idea_boxes)
        for box, _ident in self._idea_boxes:
            box.setChecked(wanted)
        self._sync()

    @staticmethod
    def _master_state(boxes: list[tuple[QCheckBox, int]]) -> Qt.CheckState:
        if not boxes:
            return Qt.CheckState.Unchecked
        ticked = sum(1 for box, _ in boxes if box.isChecked())
        if ticked == 0:
            return Qt.CheckState.Unchecked
        if ticked == len(boxes):
            return Qt.CheckState.Checked
        return Qt.CheckState.PartiallyChecked

    def _sync(self) -> None:
        self.all_apps.blockSignals(True)
        self.all_apps.setCheckState(self._master_state(self._app_boxes))
        self.all_apps.blockSignals(False)

        self.all_ideas.blockSignals(True)
        self.all_ideas.setCheckState(self._master_state(self._idea_boxes))
        self.all_ideas.blockSignals(False)

        self.export_button.setEnabled(bool(self.selected_app_ids or self.selected_idea_ids))

    @property
    def selected_app_ids(self) -> list[int]:
        return [ident for box, ident in self._app_boxes if box.isChecked()]

    @property
    def selected_idea_ids(self) -> list[int]:
        return [ident for box, ident in self._idea_boxes if box.isChecked()]

    # ---------- exporting ----------

    def _choose_destination(self) -> None:
        chosen, _filter = QFileDialog.getSaveFileName(
            self, "Export portfolio", self.path_field.text(), "PDF (*.pdf)"
        )
        if chosen:
            if not chosen.lower().endswith(".pdf"):
                chosen += ".pdf"
            self.path_field.setText(chosen)

    def gather(self) -> Portfolio:
        """Read everything the PDF needs, here on the main thread.

        The renderer runs on a worker and must never touch the store.
        """
        portfolio = Portfolio(made_on=timefmt.today_eyebrow())

        for app_id in self.selected_app_ids:
            app = self.store.get_app(app_id)
            if app is None:
                continue
            shots = [
                a.stored_path
                for a in self.store.list_attachments(app.id, images=True)
            ]
            portfolio.apps.append(
                AppPage(
                    name=app.name,
                    description=app.description,
                    github_url=app.github_url,
                    version_label=app.version_label,
                    shipped=app.shipped,
                    open_features=self.store.sheet_counts(app.id, FEATURE).open,
                    screenshots=shots,
                )
            )

        for idea_id in self.selected_idea_ids:
            idea = self.store.get_idea(idea_id)
            if idea is None:
                continue
            portfolio.ideas.append(
                IdeaLine(
                    title=idea.title, jotted=timefmt.on_date(idea.created_at)
                )
            )

        return portfolio

    def _export(self) -> None:
        if self._busy:
            return
        portfolio = self.gather()
        if portfolio.is_empty:
            return
        destination = self.path_field.text().strip() or str(default_destination())

        self._busy = True
        self.export_button.setEnabled(False)
        self.export_button.setText("writing…")
        self.open_it.setVisible(False)
        self.result.setVisible(False)

        def work() -> str:
            return str(write_portfolio(portfolio, destination))

        run_off_thread(work, self._finished, self._failed)

    def _finished(self, written: object) -> None:
        self._busy = False
        self.export_button.setText("Export PDF")
        self._sync()
        self._written = Path(str(written))
        self.result.setText(f"Written to {self._written}")
        self.result.setVisible(True)
        self.open_it.setVisible(True)
        self.exported.emit(str(written))

    def _failed(self, message: str) -> None:
        self._busy = False
        self.export_button.setText("Export PDF")
        self._sync()
        self.result.setText(f"The PDF could not be written. {message}")
        self.result.setVisible(True)
        self.open_it.setVisible(False)

    def _open_result(self) -> None:
        if self._written is not None:
            open_with_the_system(self._written)


def _field_label(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("FieldLabel")
    font = label.font()
    font.setLetterSpacing(font.SpacingType.PercentageSpacing, 114)
    label.setFont(font)
    return label
