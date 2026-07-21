"""Apps list, App Detail, sheets, and managed attachments."""

from __future__ import annotations

from pathlib import Path

import pytest

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
def always_confirm(monkeypatch):
    monkeypatch.setattr(
        "dig.ui.dialogs.ConfirmDialog.ask", staticmethod(lambda *a, **k: True)
    )


@pytest.fixture
def never_confirm(monkeypatch):
    monkeypatch.setattr(
        "dig.ui.dialogs.ConfirmDialog.ask", staticmethod(lambda *a, **k: False)
    )


@pytest.fixture
def png(tmp_path: Path):
    """A real PNG on disk, so thumbnails have something to load."""
    from PySide6.QtGui import QImage

    def _make(name: str, colour: int = 0xFF3366) -> Path:
        folder = tmp_path / "shots"
        folder.mkdir(exist_ok=True)
        path = folder / name
        image = QImage(40, 24, QImage.Format.Format_RGB32)
        image.fill(colour)
        image.save(str(path))
        return path

    return _make


# ---------- apps list ----------


def test_apps_empty_state(window):
    window.go_to("apps")
    screen = window.screens["apps"]
    assert screen.empty.isVisible()
    assert "No apps yet" in screen.empty.text()


def test_apps_are_listed_with_their_open_counts(window, store: Store):
    app = store.create_app("Local AI Hub", description="Control panel", shipped=True)
    store.add_sheet_item(app.id, FEATURE, "Disk usage per model")
    store.add_sheet_item(app.id, FEATURE, "Log bundle")
    done = store.add_sheet_item(app.id, FEATURE, "Already done")
    store.add_sheet_item(app.id, BUG, "Lamp goes stale")
    assert done is not None
    store.toggle_sheet_item(done.id)

    window.go_to("apps")
    screen = window.screens["apps"]

    assert len(screen._rows) == 1
    row = screen._rows[0]
    labels = [c.text() for c in row.findChildren(type(screen.empty))]
    assert "2 features open · 1 bugs open" in labels
    assert "SHIPPED" in labels


def test_opening_an_app_shows_its_detail(window, store: Store):
    app = store.create_app("Bearings", description="A field guide")
    window.open_app(app.id)

    assert window.current_screen_key == "app_detail"
    detail = window.screens["app_detail"]
    assert detail.name_field.text() == "Bearings"
    assert detail.description_field.toPlainText() == "A field guide"
    assert window.rail.nav_items["apps"].property("active") is True


# ---------- app detail header ----------


def test_chips_appear_only_when_they_mean_something(window, store: Store):
    plain = store.create_app("Plain")
    window.open_app(plain.id)
    detail = window.screens["app_detail"]
    assert not detail.shipped_chip.isVisible()
    assert not detail.version_chip.isVisible()
    assert not detail.github_link.isVisible()

    full = store.create_app(
        "Full", shipped=True, version_label="v1.2.0",
        github_url="https://github.com/kamsiob/full",
    )
    window.open_app(full.id)
    assert detail.shipped_chip.isVisible()
    assert detail.version_chip.isVisible()
    assert detail.version_chip.text() == "V1.2.0"
    assert detail.github_link.isVisible()
    assert detail.github_field.text() == "https://github.com/kamsiob/full"


def test_the_origin_callout_only_shows_for_a_promoted_app(window, store: Store):
    direct = store.create_app("Added directly")
    window.open_app(direct.id)
    detail = window.screens["app_detail"]
    assert not detail.origin.isVisible()

    idea = store.create_idea("One place to start the local AI stuff")
    assert idea is not None
    promoted = store.promote_idea(idea.id, "Local AI Hub")
    window.open_app(promoted.id)

    assert detail.origin.isVisible()
    assert detail.origin_tag.text().startswith("DUG FROM AN IDEA · JOTTED ")
    assert "One place to start the local AI stuff" in detail.origin_text.text()


def test_header_edits_save_themselves(window, qtbot, store: Store):
    app = store.create_app("Before")
    window.open_app(app.id)
    detail = window.screens["app_detail"]

    detail.name_field.setText("After")
    detail.name_field.textEdited.emit("After")
    detail.save_now()

    saved = store.get_app(app.id)
    assert saved is not None and saved.name == "After"


def test_an_app_never_loses_its_name(window, store: Store):
    app = store.create_app("Keeps its name")
    window.open_app(app.id)
    detail = window.screens["app_detail"]

    detail.name_field.setText("   ")
    detail.save_now()

    saved = store.get_app(app.id)
    assert saved is not None and saved.name == "Keeps its name"
    assert detail.name_field.text() == "Keeps its name"


def test_shipped_toggles_from_the_detail(window, store: Store):
    app = store.create_app("Ship me")
    window.open_app(app.id)
    detail = window.screens["app_detail"]
    assert detail.shipped_toggle.text() == "Mark shipped"

    detail.shipped_toggle.click()

    saved = store.get_app(app.id)
    assert saved is not None and saved.shipped is True
    assert detail.shipped_chip.isVisible()
    assert detail.shipped_toggle.text() == "Unmark shipped"


def test_notes_keep_their_line_breaks(window, store: Store):
    app = store.create_app("Notes")
    window.open_app(app.id)
    detail = window.screens["app_detail"]

    detail.notes_field.setPlainText("para one\n\npara two\nline three")
    detail.save_now()

    saved = store.get_app(app.id)
    assert saved is not None
    assert saved.notes == "para one\n\npara two\nline three"


# ---------- sheets ----------


def test_adding_a_line_puts_it_on_top(window, store: Store):
    app = store.create_app("Sheets")
    window.open_app(app.id)
    sheet = window.screens["app_detail"].features

    sheet.begin_add()
    assert sheet.add_field.isVisible()
    sheet.add_field.setText("First feature")
    sheet.add_field.committed.emit("First feature")
    sheet.add_field.setText("Second feature")
    sheet.add_field.committed.emit("Second feature")

    assert [line.item.text for line in sheet._lines] == [
        "Second feature",
        "First feature",
    ]
    assert sheet.count.text() == "2 open · 0 done"


def test_escape_cancels_an_inline_add(window, store: Store):
    app = store.create_app("Sheets")
    window.open_app(app.id)
    sheet = window.screens["app_detail"].bugs

    sheet.begin_add()
    sheet.add_field.setText("Never committed")
    sheet.add_field.cancelled.emit()

    assert not sheet.add_field.isVisible()
    assert sheet.add_link.isVisible()
    assert store.list_sheet_items(app.id, BUG) == []


def test_an_empty_line_is_not_added(window, store: Store):
    app = store.create_app("Sheets")
    window.open_app(app.id)
    sheet = window.screens["app_detail"].features

    sheet.begin_add()
    sheet.add_field.committed.emit("   ")

    assert store.list_sheet_items(app.id, FEATURE) == []


def test_toggling_marks_done_and_sinks_it(window, store: Store):
    app = store.create_app("Sheets")
    first = store.add_sheet_item(app.id, FEATURE, "First")
    store.add_sheet_item(app.id, FEATURE, "Second")
    assert first is not None
    window.open_app(app.id)
    sheet = window.screens["app_detail"].features

    line = next(line for line in sheet._lines if line.item.text == "First")
    line.toggled.emit(line.item.id)

    assert [line.item.text for line in sheet._lines] == ["Second", "First"]
    assert sheet._lines[-1].item.done is True
    assert sheet._lines[-1].item.done_at is not None
    assert sheet.count.text() == "1 open · 1 done"


def test_toggling_back_clears_done(window, store: Store):
    app = store.create_app("Sheets")
    item = store.add_sheet_item(app.id, BUG, "Toggle me")
    assert item is not None
    window.open_app(app.id)
    sheet = window.screens["app_detail"].bugs

    sheet._toggle(item.id)
    assert store.get_sheet_item(item.id).done is True

    sheet._toggle(item.id)
    refreshed = store.get_sheet_item(item.id)
    assert refreshed.done is False
    assert refreshed.done_at is None
    assert sheet.count.text() == "1 open · 0 done"


def test_removing_a_line_needs_no_confirm(window, store: Store):
    """A one-liner costs seconds to retype; a dialog costs more."""
    app = store.create_app("Sheets")
    item = store.add_sheet_item(app.id, BUG, "Delete me")
    assert item is not None
    window.open_app(app.id)
    sheet = window.screens["app_detail"].bugs

    sheet._remove(item.id)

    assert store.get_sheet_item(item.id) is None
    assert sheet._lines == []


def test_sheets_have_nothing_a_project_manager_would_add(window, store: Store):
    """No priority, status, due date, or assignee anywhere on a sheet."""
    app = store.create_app("Sheets")
    store.add_sheet_item(app.id, FEATURE, "A feature")
    window.open_app(app.id)
    sheet = window.screens["app_detail"].features

    from PySide6.QtWidgets import QLabel

    words = " ".join(
        label.text().lower() for label in sheet.findChildren(QLabel)
    )
    for banned in ("priority", "status", "due", "assignee", "sprint", "estimate"):
        assert banned not in words


# ---------- attachments ----------


def test_attaching_an_image_copies_it_in(window, store: Store, png, qtbot):
    app = store.create_app("Shots")
    window.open_app(app.id)
    section = window.screens["app_detail"].screenshots
    source = png("home.png")

    section.attach_paths([str(source)])
    wait_for_disk_work()
    qtbot.waitUntil(lambda: len(store.list_attachments(app.id, images=True)) == 1)

    assert source.exists(), "the original is never moved"
    stored = Path(store.list_attachments(app.id, images=True)[0].stored_path)
    assert stored.is_file()
    assert stored.parent == store.app_attachments_dir(app.id)


def test_images_and_files_go_to_their_own_sections(window, store: Store, png, qtbot):
    app = store.create_app("Both")
    window.open_app(app.id)
    detail = window.screens["app_detail"]

    store.attach_file(app.id, png("shot.png"))
    notes = store.app_attachments_dir(app.id).parent / "notes.md"
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text("release notes")
    store.attach_file(app.id, notes)
    detail.refresh()

    assert len(detail.screenshots._items) == 1
    assert len(detail.attachments._items) == 1
    assert detail.screenshots._items[0].attachment.filename == "shot.png"
    assert detail.attachments._items[0].attachment.filename == "notes.md"


def test_removing_an_attachment_deletes_the_stored_copy(
    window, store: Store, png, always_confirm
):
    app = store.create_app("Shots")
    attachment = store.attach_file(app.id, png("gone.png"))
    stored = Path(attachment.stored_path)
    window.open_app(app.id)
    section = window.screens["app_detail"].screenshots

    section._remove(attachment.id)

    assert not stored.exists()
    assert store.get_attachment(attachment.id) is None


def test_cancelling_a_removal_keeps_the_file(
    window, store: Store, png, never_confirm
):
    app = store.create_app("Shots")
    attachment = store.attach_file(app.id, png("stays.png"))
    window.open_app(app.id)
    section = window.screens["app_detail"].screenshots

    section._remove(attachment.id)

    assert Path(attachment.stored_path).exists()
    assert store.get_attachment(attachment.id) is not None


def test_same_named_files_get_suffixes(window, store: Store, png, qtbot):
    app = store.create_app("Collisions")
    window.open_app(app.id)
    section = window.screens["app_detail"].screenshots
    source = png("shot.png")

    section.attach_paths([str(source)])
    wait_for_disk_work()
    section.attach_paths([str(source)])
    wait_for_disk_work()
    qtbot.waitUntil(lambda: len(store.list_attachments(app.id, images=True)) == 2)

    names = [a.filename for a in store.list_attachments(app.id, images=True)]
    assert names == ["shot.png", "shot-2.png"]


def test_staging_a_file_touches_no_database(store: Store, png):
    """The part that runs on a worker thread must not use the connection.

    A sqlite3 connection belongs to the thread that opened it, so a copy that
    also wrote its row would fail on the worker and be swallowed as a
    background error, losing the attachment silently.
    """
    import threading

    app = store.create_app("Threaded")
    source = png("from-a-thread.png")
    landed: list[Path] = []
    failed: list[str] = []

    def worker() -> None:
        try:
            landed.append(store.stage_attachment(app.id, source))
        except Exception as problem:  # noqa: BLE001 - the point of the test
            failed.append(str(problem))

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=10)

    assert failed == [], f"staging must be thread-safe, got: {failed}"
    assert len(landed) == 1 and landed[0].is_file()

    # Recording it belongs on the owning thread, and completes the attachment.
    attachment = store.record_attachment(app.id, landed[0])
    assert attachment.filename == "from-a-thread.png"
    assert attachment.is_image is True
    assert source.exists(), "the original is never moved"


# ---------- deleting an app ----------


def test_deleting_an_app_warns_about_its_attachments(
    window, store: Store, png, monkeypatch
):
    app = store.create_app("Doomed")
    store.attach_file(app.id, png("a.png"))
    store.attach_file(app.id, png("b.png"))
    window.open_app(app.id)

    asked: list[str] = []

    def capture(_parent, _palette, question, confirm_label="Delete"):
        asked.append(question)
        return False

    monkeypatch.setattr("dig.ui.dialogs.ConfirmDialog.ask", staticmethod(capture))
    window.screens["app_detail"]._delete_app()

    assert len(asked) == 1
    assert "Doomed" in asked[0]
    assert "2 attached files are deleted too" in asked[0]
    assert store.get_app(app.id) is not None, "cancelling changes nothing"


def test_deleting_an_app_removes_its_folder(
    window, store: Store, png, qtbot, always_confirm
):
    app = store.create_app("Doomed")
    store.attach_file(app.id, png("a.png"))
    folder = store.app_attachments_dir(app.id)
    assert folder.is_dir()
    window.open_app(app.id)

    window.screens["app_detail"]._delete_app()
    wait_for_disk_work()
    qtbot.waitUntil(lambda: store.get_app(app.id) is None)

    assert not folder.exists()
    assert store.conn.execute("SELECT COUNT(*) FROM attachments").fetchone()[0] == 0


def test_open_counts_survive_a_round_trip(window, store: Store):
    """The Apps list reflects what the detail screen changed."""
    app = store.create_app("Counted")
    window.open_app(app.id)
    sheet = window.screens["app_detail"].features
    sheet.begin_add()
    sheet.add_field.committed.emit("A new feature")

    window.go_to("apps")
    labels = [
        c.text()
        for row in window.screens["apps"]._rows
        for c in row.findChildren(type(window.screens["apps"].empty))
    ]
    assert "1 features open · 0 bugs open" in labels
