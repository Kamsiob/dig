"""The Export screen and the PDF it writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from dig.export import Portfolio, write_portfolio
from dig.storage import BUG, FEATURE, Store
from dig.theme import LIGHT_MODE, ThemeManager
from dig.ui.window import MainWindow
from dig.ui.work import wait_for_disk_work


@pytest.fixture
def window(qtbot, store: Store):
    w = MainWindow(store, ThemeManager(LIGHT_MODE))
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    return w


@pytest.fixture
def export(window, qtbot):
    window.go_to("export")
    return window.screens["export"]


@pytest.fixture
def png(tmp_path: Path):
    from PySide6.QtGui import QImage

    def _make(name: str, colour: int = 0x336699) -> Path:
        folder = tmp_path / "shots"
        folder.mkdir(exist_ok=True)
        path = folder / name
        image = QImage(320, 200, QImage.Format.Format_RGB32)
        image.fill(colour)
        image.save(str(path))
        return path

    return _make


def page_count(pdf: Path) -> int:
    """Count pages without another dependency: /Type /Page objects."""
    raw = pdf.read_bytes()
    return raw.count(b"/Type /Page") - raw.count(b"/Type /Pages")


# ---------- selection ----------


def test_shipped_apps_start_ticked_and_ideas_do_not(export, store: Store):
    store.create_app("Shipped one", shipped=True)
    store.create_app("Not shipped")
    store.create_idea("An idea")
    export.refresh()

    ticked = {
        box.text() for box, _ident in export._app_boxes if box.isChecked()
    }
    assert ticked == {"Shipped one"}
    assert all(not box.isChecked() for box, _ in export._idea_boxes)


def test_export_is_disabled_until_something_is_chosen(export, store: Store):
    store.create_app("Not shipped")
    store.create_idea("An idea")
    export.refresh()

    assert not export.export_button.isEnabled()

    export._app_boxes[0][0].setChecked(True)
    assert export.export_button.isEnabled()

    export._app_boxes[0][0].setChecked(False)
    assert not export.export_button.isEnabled()

    export._idea_boxes[0][0].setChecked(True)
    assert export.export_button.isEnabled(), "ideas alone are enough"


def test_the_master_checkbox_takes_the_whole_group(export, store: Store):
    for n in range(3):
        store.create_app(f"App {n}")
    export.refresh()
    assert len(export.selected_app_ids) == 0

    export._toggle_all_apps()
    assert len(export.selected_app_ids) == 3

    export._toggle_all_apps()
    assert len(export.selected_app_ids) == 0


def test_the_master_shows_a_partial_state(export, store: Store):
    from PySide6.QtCore import Qt

    store.create_app("One", shipped=True)
    store.create_app("Two")
    export.refresh()

    assert export.all_apps.checkState() == Qt.CheckState.PartiallyChecked

    export._toggle_all_apps()
    assert export.all_apps.checkState() == Qt.CheckState.Checked


def test_promoted_ideas_are_not_offered(export, store: Store):
    kept = store.create_idea("Still an idea")
    promoted = store.create_idea("Became an app")
    assert kept is not None and promoted is not None
    store.promote_idea(promoted.id, "An app")
    export.refresh()

    assert [box.text() for box, _ in export._idea_boxes] == ["Still an idea"]


def test_the_default_destination_is_a_pdf(export):
    assert export.path_field.text().endswith("Dig Portfolio.pdf")


# ---------- gathering ----------


def test_gather_reads_what_the_pdf_needs(export, store: Store, png):
    app = store.create_app(
        "Local AI Hub",
        description="Control panel",
        github_url="https://github.com/kamsiob/local-ai-hub",
        version_label="v1.2.0",
        shipped=True,
    )
    store.add_sheet_item(app.id, FEATURE, "Open one")
    done = store.add_sheet_item(app.id, FEATURE, "Closed one")
    store.add_sheet_item(app.id, BUG, "A bug nobody should see")
    assert done is not None
    store.toggle_sheet_item(done.id)
    store.attach_file(app.id, png("home.png"))
    export.refresh()

    portfolio = export.gather()

    assert len(portfolio.apps) == 1
    page = portfolio.apps[0]
    assert page.name == "Local AI Hub"
    assert page.shipped is True
    assert page.version_label == "v1.2.0"
    assert page.open_features == 1
    assert len(page.screenshots) == 1
    # Nothing about bugs travels: a portfolio, not a report.
    assert not hasattr(page, "open_bugs")


def test_only_four_screenshots_reach_a_page(store: Store, png, tmp_path: Path):
    portfolio = Portfolio(made_on="Tuesday, July 21")
    from dig.export import AppPage

    shots = [str(png(f"shot{n}.png")) for n in range(6)]
    portfolio.apps.append(AppPage(name="Many shots", screenshots=shots))

    written = write_portfolio(portfolio, tmp_path / "many.pdf")
    assert written.is_file()
    assert page_count(written) == 2  # cover + one app page


# ---------- writing ----------


def test_a_known_dataset_makes_the_expected_pages(export, store: Store, png, qtbot, tmp_path):
    for n in range(2):
        app = store.create_app(f"App {n}", shipped=True, description="Does things")
        store.attach_file(app.id, png(f"a{n}.png"))
    store.create_idea("An idea\nwith a note")
    store.create_idea("Another idea")
    export.refresh()
    export._toggle_all_ideas()

    target = tmp_path / "portfolio.pdf"
    export.path_field.setText(str(target))
    export._export()
    wait_for_disk_work()
    qtbot.waitUntil(lambda: target.is_file(), timeout=10000)

    # cover + 2 apps + 1 ideas page
    assert page_count(target) == 4
    assert export.gather().page_count == 4


def test_no_ideas_page_when_no_ideas_are_chosen(export, store: Store, qtbot, tmp_path):
    store.create_app("Only app", shipped=True)
    store.create_idea("Not chosen")
    export.refresh()

    target = tmp_path / "apps-only.pdf"
    export.path_field.setText(str(target))
    export._export()
    wait_for_disk_work()
    qtbot.waitUntil(lambda: target.is_file(), timeout=10000)

    assert page_count(target) == 2  # cover + one app


def test_the_result_is_reported_with_a_way_to_open_it(
    export, store: Store, qtbot, tmp_path
):
    store.create_app("Only app", shipped=True)
    export.refresh()
    target = tmp_path / "reported.pdf"
    export.path_field.setText(str(target))

    assert not export.open_it.isVisible()
    export._export()
    wait_for_disk_work()
    qtbot.waitUntil(lambda: export.open_it.isVisible(), timeout=10000)

    assert str(target) in export.result.text()
    assert export.export_button.text() == "Export PDF"


def test_the_pdf_embeds_the_bundled_fonts(tmp_path: Path):
    from dig.export import AppPage

    portfolio = Portfolio(made_on="Tuesday, July 21")
    portfolio.apps.append(AppPage(name="Fonted", description="Some words"))
    written = write_portfolio(portfolio, tmp_path / "fonts.pdf")

    raw = written.read_bytes()
    for family in (b"Fraunces", b"IBMPlex"):
        assert family in raw, f"{family!r} must be embedded, not referenced"


def test_writing_touches_no_store_or_widget(store: Store, tmp_path: Path):
    """The renderer runs on a worker thread, so it must be self-contained."""
    import threading

    from dig.export import AppPage

    portfolio = Portfolio(made_on="Tuesday, July 21")
    portfolio.apps.append(AppPage(name="From a thread", description="Rendered off-thread"))
    target = tmp_path / "threaded.pdf"
    failed: list[str] = []

    def worker() -> None:
        try:
            write_portfolio(portfolio, target)
        except Exception as problem:  # noqa: BLE001 - the point of the test
            failed.append(str(problem))

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=20)

    assert failed == []
    assert target.is_file()


def test_an_unwritable_destination_is_reported_plainly(
    export, store: Store, qtbot, tmp_path
):
    store.create_app("Only app", shipped=True)
    export.refresh()
    export.path_field.setText("/proc/definitely-not-writable/portfolio.pdf")

    export._export()
    wait_for_disk_work()
    qtbot.waitUntil(lambda: export.result.isVisible(), timeout=10000)

    text = export.result.text()
    assert "could not be written" in text
    for apology in ("sorry", "oops", "unfortunately"):
        assert apology not in text.lower()
    assert not export.open_it.isVisible()
