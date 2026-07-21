"""A scripted week with Dig.

This drives the real window the way a person would: typing into the real
fields, pressing the real keys, restarting the app between sessions, and
checking what actually landed on disk afterwards.

The steps follow the order someone would meet them in: jot before promote,
promote before sheets, sheets before export.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from dig.storage import BUG, FEATURE, Store
from dig.theme import (
    APPEARANCE_KEY,
    DARK,
    DARK_MODE,
    LIGHT,
    LIGHT_MODE,
    SYSTEM_MODE,
    ThemeManager,
)
from dig.ui.capture import CaptureDialog
from dig.ui.rail import SCREENS
from dig.ui.window import MIN_HEIGHT, MIN_WIDTH, MainWindow
from dig.ui.work import wait_for_disk_work


class Session:
    """One run of the app against a profile folder that survives restarts."""

    def __init__(self, profile: Path, qtbot, mode: str = LIGHT_MODE):
        self.profile = profile
        self.qtbot = qtbot
        self.store = Store(
            db_file=profile / "dig.db", attachments_root=profile / "attachments"
        ).open()
        saved = self.store.get_setting(APPEARANCE_KEY, mode)
        self.theme = ThemeManager(saved)
        self.theme.apply()
        self.window = MainWindow(self.store, self.theme)
        qtbot.addWidget(self.window)
        # Only size the window when nothing was remembered, or the harness
        # would overwrite the very geometry the restart is meant to check.
        from dig.ui.window import GEOMETRY_KEY

        if not self.store.get_setting(GEOMETRY_KEY, ""):
            self.window.resize(1180, 820)
        self.window.show()
        qtbot.waitExposed(self.window)

    def screen(self, key: str):
        return self.window.screens[key]

    def close(self) -> None:
        self.window._save_geometry()
        self.window.close()
        self.store.close()


@pytest.fixture
def profile(tmp_path: Path) -> Path:
    """A fresh, empty data folder. Nothing has ever run here."""
    folder = tmp_path / "profile"
    folder.mkdir()
    return folder


@pytest.fixture
def no_confirm_needed(monkeypatch):
    monkeypatch.setattr(
        "dig.ui.dialogs.ConfirmDialog.ask", staticmethod(lambda *a, **k: True)
    )


@pytest.fixture
def opened_files(monkeypatch):
    """Record what would be handed to the desktop instead of really opening it."""
    seen: list[str] = []
    monkeypatch.setattr(
        "dig.ui.attachments.open_with_the_system",
        lambda path: seen.append(str(path)) or True,
    )
    return seen


def make_png(folder: Path, name: str, colour: int = 0x2E4034) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    image = QImage(320, 200, QImage.Format.Format_RGB32)
    image.fill(colour)
    image.save(str(path))
    return path


def jot(session: Session, text: str) -> None:
    """Type an idea and press Enter, with no mouse involved."""
    home = session.screen("home")
    field = home.jot.field
    field.setFocus()
    session.qtbot.keyClicks(field, text)
    session.qtbot.keyClick(field, Qt.Key.Key_Return)


# ---------- 1 to 5: jotting, restarting, resurfacing, editing ----------


def test_a_week_of_jotting_and_digging(profile, qtbot):
    # 1. A fresh profile. Every screen should say plainly that it is empty.
    first = Session(profile, qtbot)

    # Each empty state is checked while its own screen is the one on show:
    # a widget on a hidden stack page never reports itself visible.
    first.window.go_to("home")
    assert first.screen("home").recent_empty.isVisible()
    assert first.screen("home").unearthed.idea is None
    assert "Nothing old enough to unearth yet." in first.screen(
        "home"
    ).unearthed.title.text()

    first.window.go_to("ideas")
    assert first.screen("ideas").empty.isVisible()
    assert first.screen("ideas").empty.text().startswith("Nothing buried yet.")

    first.window.go_to("apps")
    assert first.screen("apps").empty.isVisible()

    first.window.go_to("export")
    assert first.screen("export").apps_empty.isVisible()
    assert first.screen("export").ideas_empty.isVisible()
    assert not first.screen("export").export_button.isEnabled()

    first.window.go_to("settings")
    assert first.screen("settings").folder_path.text().endswith("dig")

    # 2. Twelve ideas without touching the mouse, one multiline, one empty Enter.
    first.window.go_to("home")
    qtbot.waitUntil(first.screen("home").jot.field.hasFocus)

    field = first.screen("home").jot.field
    qtbot.keyClick(field, Qt.Key.Key_Return)  # the accidental one
    assert first.store.list_ideas() == [], "an empty Enter saves nothing"

    for n in range(10):
        jot(first, f"Idea number {n}")

    # Two multiline ones, using Shift+Enter for the note.
    for title, note in (
        ("Pocket wiki for the channel", "one markdown file per video"),
        ("Clipboard history that expires", "everything goes after 24h"),
    ):
        field.setFocus()
        qtbot.keyClicks(field, title)
        qtbot.keyClick(field, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        qtbot.keyClicks(field, note)
        qtbot.keyClick(field, Qt.Key.Key_Return)

    assert len(first.store.list_ideas()) == 12
    first.close()

    # 3. Restart. Everything is still there, in the right places.
    second = Session(profile, qtbot)
    assert len(second.store.list_ideas()) == 12

    second.window.go_to("home")
    home = second.screen("home")
    assert [row.idea.title for row in home._rows] == [
        "Clipboard history that expires",
        "Pocket wiki for the channel",
        "Idea number 9",
    ]
    assert home.unearthed.idea is not None
    recent_titles = {row.idea.title for row in home._rows}
    assert home.unearthed.idea.title not in recent_titles

    # 4. Dig again eight times: never an immediate repeat, and it moves around.
    seen = {home.unearthed.idea.id}
    for _ in range(8):
        before = home.unearthed.idea.id
        home.dig_again()
        assert home.unearthed.idea is not None
        assert home.unearthed.idea.id != before, "never the one already showing"
        seen.add(home.unearthed.idea.id)
    assert len(seen) > 2, "the draw should move around the pool"

    # 5. Open an unearthed idea, change it, come back.
    target = home.unearthed.idea
    assert target.never_opened
    home.unearthed.open_button.click()
    assert second.window.current_screen_key == "idea_editor"

    editor = second.screen("idea_editor")
    editor.title_field.setText("Reworked title")
    editor.title_field.textEdited.emit("Reworked title")
    editor.note_field.setPlainText("Reworked note, with more detail.")
    second.window.go_to("home")  # leaving flushes the save

    saved = second.store.get_idea(target.id)
    assert saved.title == "Reworked title"
    assert saved.note == "Reworked note, with more detail."
    assert not saved.never_opened, "opening it stamped when it was last seen"

    second.close()


# ---------- 6 to 9: promoting, capturing, working the sheets ----------


def test_promoting_capturing_and_working_the_sheets(profile, qtbot):
    session = Session(profile, qtbot)
    for n in range(6):
        session.store.create_idea(f"Idea number {n}\nwith a note")

    # 6. Promote three ideas, then add one app by hand.
    ideas = session.store.list_ideas()
    promoted_names = []
    for idea in ideas[:3]:
        session.window.promote_idea(idea.id)
        editor = session.screen("app_editor")
        assert editor.name_field.text() == idea.title
        assert editor.description_field.toPlainText() == idea.note
        editor.create_button.click()
        promoted_names.append(idea.title)

    session.window.new_app()
    manual = session.screen("app_editor")
    assert manual.name_field.text() == "", "the editor does not leak the last idea"
    manual.name_field.setText("Bearings")
    manual.github_field.setText("https://github.com/kamsiob/bearings")
    manual.shipped_box.setChecked(True)
    manual.create_button.click()

    apps = session.store.list_apps()
    assert len(apps) == 4
    # list_apps is alphabetical, which is what every picker shows, so apps are
    # looked up by name rather than by the order they were created in.
    by_name = {a.name: a for a in apps}
    bearings = by_name["Bearings"]
    first_app = by_name[promoted_names[0]]
    second_app = by_name[promoted_names[1]]
    assert bearings.shipped is True
    assert bearings.origin_idea_id is None
    for name in promoted_names:
        assert next(a for a in apps if a.name == name).origin_idea_id is not None

    # 7. The promoted ideas are out of the ledger until asked for.
    session.window.go_to("ideas")
    ledger = session.screen("ideas")
    shown = [row.idea.title for row in ledger._rows]
    assert all(name not in shown for name in promoted_names)

    ledger.show_promoted.setChecked(True)
    with_promoted = [row.idea.title for row in ledger._rows]
    for name in promoted_names:
        assert name in with_promoted
    dimmed = next(r for r in ledger._rows if r.idea.title == promoted_names[0])
    assert dimmed._read_only
    assert dimmed.suffix.text().startswith("→ ")

    # 8. Ctrl K from Settings: four features and three bugs, keyboard only.
    session.window.go_to("settings")
    plan = [
        (FEATURE, "Disk usage per model", first_app.id),
        (FEATURE, "One-click log bundle", first_app.id),
        (FEATURE, "Export the manifest", second_app.id),
        (FEATURE, "Keyboard shortcuts page", bearings.id),
        (BUG, "Status lamp goes stale", first_app.id),
        (BUG, "Warning fires twice", second_app.id),
        (BUG, "Window grouping on Wayland", bearings.id),
    ]
    for kind, text, app_id in plan:
        dialog = CaptureDialog(
            session.store,
            session.theme.palette,
            session.window._last_captured_app_id,
            session.window,
        )
        dialog.captured.connect(session.window._on_captured)
        qtbot.addWidget(dialog)
        dialog.show()
        # Focus-on-open is asserted in the capture tests; here the point is
        # the run of captures, so the field is simply claimed and typed into.
        dialog.text_field.setFocus()
        qtbot.wait(5)

        if kind == BUG:
            dialog.kind_toggle.toggle()
        qtbot.keyClicks(dialog.text_field, text)
        dialog.app_picker.setCurrentIndex(dialog.app_picker.findData(app_id))
        qtbot.keyClick(dialog, Qt.Key.Key_Return)
        dialog.close()

    assert session.store.sheet_counts(first_app.id, FEATURE).open == 2
    assert session.store.sheet_counts(first_app.id, BUG).open == 1
    assert session.store.sheet_counts(second_app.id, FEATURE).open == 1
    assert session.store.sheet_counts(bearings.id, FEATURE).open == 1
    assert session.store.sheet_counts(bearings.id, BUG).open == 1
    assert session.window._last_captured_app_id == bearings.id

    # 9. Work one app's sheets: toggle, untoggle, add inline, delete a line.
    session.window.open_app(first_app.id)
    detail = session.screen("app_detail")
    features = detail.features

    first_line = features._lines[0]
    features._toggle(first_line.item.id)
    assert features.count.text() == "1 open · 1 done"
    assert features._lines[-1].item.done, "done sinks to the bottom"

    features._toggle(features._lines[-1].item.id)
    assert features.count.text() == "2 open · 0 done"
    assert session.store.get_sheet_item(first_line.item.id).done_at is None

    features.begin_add()
    features.add_field.committed.emit("Added from the sheet itself")
    assert features._lines[0].item.text == "Added from the sheet itself"
    assert features.count.text() == "3 open · 0 done"

    bug_line = detail.bugs._lines[0]
    detail.bugs._remove(bug_line.item.id)
    assert detail.bugs._lines == []
    assert detail.bugs.count.text() == "0 open · 0 done"

    session.close()


# ---------- 10 to 11: attachments and notes that survive a restart ----------


def test_attachments_and_notes_survive(profile, qtbot, tmp_path, opened_files,
                                       no_confirm_needed):
    session = Session(profile, qtbot)
    app = session.store.create_app("Local AI Hub")
    session.window.open_app(app.id)
    detail = session.screen("app_detail")

    # 10. Three images and two files, two of which share a name.
    sources = tmp_path / "sources"
    images = [make_png(sources, f"shot{n}.png", 0x2E4034 + n * 0x2000) for n in range(3)]
    detail.screenshots.attach_paths([str(p) for p in images])
    wait_for_disk_work()
    qtbot.waitUntil(lambda: len(detail.screenshots._items) == 3, timeout=10000)

    notes_a = sources / "notes.md"
    notes_a.write_text("first notes")
    detail.attachments.attach_paths([str(notes_a)])
    wait_for_disk_work()
    notes_a.write_text("second notes, same filename")
    detail.attachments.attach_paths([str(notes_a)])
    wait_for_disk_work()
    qtbot.waitUntil(lambda: len(detail.attachments._items) == 2, timeout=10000)

    stored_names = [a.filename for a in session.store.list_attachments(app.id, images=False)]
    assert stored_names == ["notes.md", "notes-2.md"], "a collision takes a suffix"
    stored = session.store.list_attachments(app.id, images=False)
    assert Path(stored[0].stored_path).read_text() == "first notes"
    assert Path(stored[1].stored_path).read_text() == "second notes, same filename"
    for original in images + [notes_a]:
        assert original.exists(), "originals are never moved"

    # Open one of each through the desktop.
    detail.screenshots._open(session.store.list_attachments(app.id, images=True)[0].id)
    detail.attachments._open(stored[0].id)
    assert len(opened_files) == 2
    assert opened_files[0].endswith("shot0.png")
    assert opened_files[1].endswith("notes.md")

    # Remove one and confirm the stored copy goes with it.
    doomed = session.store.list_attachments(app.id, images=True)[0]
    doomed_path = Path(doomed.stored_path)
    detail.screenshots._remove(doomed.id)
    assert not doomed_path.exists()
    assert len(session.store.list_attachments(app.id, images=True)) == 2

    # 11. Multi-paragraph notes.
    detail.notes_field.setPlainText(
        "Lead with the hash-verification story.\n\n"
        "Demo order:\n  service control\n  model install\n  crash surfacing"
    )
    detail.save_now()
    session.close()

    # Restart and read them back exactly.
    again = Session(profile, qtbot)
    again.window.open_app(app.id)
    reopened = again.screen("app_detail")
    assert reopened.notes_field.toPlainText() == (
        "Lead with the hash-verification story.\n\n"
        "Demo order:\n  service control\n  model install\n  crash surfacing"
    )
    assert len(again.store.list_attachments(app.id)) == 4
    again.close()


# ---------- 12: the portfolio ----------


def test_exporting_a_portfolio(profile, qtbot, tmp_path):
    session = Session(profile, qtbot)
    for n in range(2):
        app = session.store.create_app(
            f"App {n}",
            description="Does a useful thing, locally.",
            github_url=f"https://github.com/kamsiob/app-{n}",
            shipped=True,
        )
        session.store.add_sheet_item(app.id, FEATURE, "Still to do")
        session.store.attach_file(app.id, make_png(tmp_path / "src", f"a{n}.png"))
    session.store.create_idea("An idea in the ground")
    session.store.create_idea("Another one")

    session.window.go_to("export")
    export = session.screen("export")
    assert len(export.selected_app_ids) == 2, "shipped apps start ticked"
    assert export.selected_idea_ids == [], "ideas are opt-in"
    export._toggle_all_ideas()

    target = tmp_path / "Dig Portfolio.pdf"
    export.path_field.setText(str(target))
    export._export()
    wait_for_disk_work()
    qtbot.waitUntil(lambda: target.is_file(), timeout=20000)
    qtbot.waitUntil(lambda: export.open_it.isVisible(), timeout=10000)

    raw = target.read_bytes()
    pages = raw.count(b"/Type /Page") - raw.count(b"/Type /Pages")
    assert pages == 4, "cover, two apps, and the ideas page"

    assert b"Fraunces" in raw and b"IBMPlex" in raw, "fonts are embedded"
    assert b"/Image" in raw, "the screenshots made it in"
    assert str(target) in export.result.text()

    session.close()


# ---------- 13: appearance ----------


def test_appearance_switches_and_is_remembered(profile, qtbot, monkeypatch):
    session = Session(profile, qtbot)

    session.window.set_appearance(LIGHT_MODE)
    assert session.theme.palette is LIGHT
    session.window.set_appearance(DARK_MODE)
    assert session.theme.palette is DARK

    session.window.set_appearance(SYSTEM_MODE)
    monkeypatch.setattr(ThemeManager, "system_is_dark", staticmethod(lambda: True))
    session.theme._on_system_scheme_changed()
    assert session.theme.palette is DARK, "System follows the desktop"

    monkeypatch.setattr(ThemeManager, "system_is_dark", staticmethod(lambda: False))
    session.theme._on_system_scheme_changed()
    assert session.theme.palette is LIGHT

    session.close()

    # The choice survives a restart.
    again = Session(profile, qtbot)
    assert again.theme.mode == SYSTEM_MODE
    assert again.window.rail.segmented._buttons[SYSTEM_MODE].property("active") is True
    assert again.screen("settings").segmented._buttons[SYSTEM_MODE].property("active")
    again.close()

    # And so does a fixed one.
    third = Session(profile, qtbot)
    third.window.set_appearance(DARK_MODE)
    third.close()
    fourth = Session(profile, qtbot)
    assert fourth.theme.mode == DARK_MODE
    assert fourth.theme.palette is DARK
    fourth.close()


# ---------- 14: deleting an app ----------


def test_deleting_an_app_takes_everything_with_it(profile, qtbot, tmp_path, monkeypatch):
    session = Session(profile, qtbot)
    app = session.store.create_app("Doomed")
    session.store.add_sheet_item(app.id, FEATURE, "Never finished")
    session.store.attach_file(app.id, make_png(tmp_path / "src", "one.png"))
    session.store.attach_file(app.id, make_png(tmp_path / "src", "two.png"))
    folder = session.store.app_attachments_dir(app.id)
    assert folder.is_dir()

    asked: list[str] = []

    def capture_question(_parent, _palette, question, confirm_label="Delete"):
        asked.append(question)
        return True

    monkeypatch.setattr(
        "dig.ui.dialogs.ConfirmDialog.ask", staticmethod(capture_question)
    )

    session.window.open_app(app.id)
    session.screen("app_detail")._delete_app()
    wait_for_disk_work()
    qtbot.waitUntil(lambda: session.store.get_app(app.id) is None, timeout=10000)

    assert len(asked) == 1
    assert "Doomed" in asked[0]
    assert "2 attached files are deleted too" in asked[0]
    assert not folder.exists()
    assert session.store.conn.execute(
        "SELECT COUNT(*) FROM sheet_items"
    ).fetchone()[0] == 0
    # Leaving the detail screen happens on the signal the worker sends back.
    qtbot.waitUntil(
        lambda: session.window.current_screen_key == "apps", timeout=10000
    )
    session.close()


# ---------- 15: window geometry ----------


def test_the_window_remembers_its_size_and_holds_its_layout(profile, qtbot):
    from PySide6.QtGui import QGuiApplication

    available = QGuiApplication.primaryScreen().availableGeometry()
    target_height = min(760, available.height() - 40)

    session = Session(profile, qtbot)
    session.window.resize(session.window.width(), target_height)
    qtbot.waitUntil(lambda: session.window.height() == target_height)
    session.close()

    again = Session(profile, qtbot)
    assert again.window.height() == target_height

    # At the smallest size the layout still holds together.
    again.window.resize(MIN_WIDTH, MIN_HEIGHT)
    qtbot.waitUntil(lambda: again.window.width() == MIN_WIDTH)
    assert again.window.rail.width() == 216
    for key, _label, _hint in SCREENS:
        again.window.go_to(key)
        screen = again.screen(key)
        assert screen.width() > 0 and screen.height() > 0
        # Content must never be pushed off the left edge.
        assert screen.mapTo(again.window, screen.rect().topLeft()).x() >= 216
    again.close()


# ---------- 16: a broken database ----------


def test_a_corrupt_database_is_recovered_with_a_notice(profile, qtbot):
    session = Session(profile, qtbot)
    session.store.create_idea("Written before the damage")
    session.close()

    (profile / "dig.db").write_bytes(b"not a database at all" * 200)

    store = Store(
        db_file=profile / "dig.db", attachments_root=profile / "attachments"
    ).open()
    assert store.recovery_notice is not None

    theme = ThemeManager(LIGHT_MODE)
    theme.apply()
    window = MainWindow(store, theme)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.show_notice(store.recovery_notice)

    assert window.notice.isVisible()
    text = window.notice.message.text()
    assert "started a fresh one" in text
    assert "dig.db.broken-" in text
    for apology in ("sorry", "oops", "unfortunately", "!"):
        assert apology not in text.lower()

    # The app still works, and the unreadable file was kept.
    assert store.list_ideas() == []
    store.create_idea("Written after the recovery")
    assert len(store.list_ideas()) == 1
    assert len(list(profile.glob("dig.db.broken-*"))) == 1

    window.close()
    store.close()


# ---------- 17: reduced motion ----------


def test_reduced_motion_suppresses_the_highlight(profile, qtbot, monkeypatch):
    monkeypatch.setattr("dig.screens.home.prefers_reduced_motion", lambda: True)
    session = Session(profile, qtbot)
    session.window.go_to("home")

    jot(session, "Kept quietly")

    row = session.screen("home")._rows[0]
    assert row.styleSheet() == ""
    session.close()


# ---------- 18: both palettes, every screen ----------


def test_every_screen_holds_up_in_both_palettes(profile, qtbot, tmp_path):
    from PySide6.QtWidgets import QLabel

    session = Session(profile, qtbot)
    idea = session.store.create_idea("An idea\nwith a note")
    for n in range(4):
        session.store.create_idea(f"Filler {n}")
    app = session.store.promote_idea(idea.id, "Local AI Hub", "Does things")
    session.store.add_sheet_item(app.id, FEATURE, "A feature")
    session.store.add_sheet_item(app.id, BUG, "A bug")
    session.store.attach_file(app.id, make_png(tmp_path / "src", "shot.png"))

    allowed_families = {"Fraunces", "IBM Plex Sans", "IBM Plex Mono"}

    for mode, palette in ((LIGHT_MODE, LIGHT), (DARK_MODE, DARK)):
        session.window.set_appearance(mode)
        assert session.theme.palette is palette

        for key in [k for k, _l, _h in SCREENS] + ["idea_editor", "app_detail"]:
            if key == "idea_editor":
                session.window.open_idea(idea.id)
            elif key == "app_detail":
                session.window.open_app(app.id)
            else:
                session.window.go_to(key)

            screen = session.screen(key)
            # Every visible word is in a bundled family, in both palettes.
            for label in screen.findChildren(QLabel):
                if label.text().strip() and label.isVisible():
                    assert label.fontInfo().family() in allowed_families

            # Nothing is styled with a rounded corner or a gradient.
            sheet = screen.styleSheet()
            assert "gradient" not in sheet.lower()

    session.close()


# ---------- 19: the links out ----------


def test_every_about_link_goes_where_it_says(profile, qtbot, monkeypatch):
    from dig.ui.about import LINKS, AboutDialog

    session = Session(profile, qtbot)
    opened: list[str] = []
    monkeypatch.setattr(
        "dig.ui.about.open_link", lambda url: opened.append(url) or True
    )

    dialog = AboutDialog(session.theme.palette, session.window)
    qtbot.addWidget(dialog)
    for button in dialog.link_buttons:
        button.click()

    assert opened == [
        "https://youtube.com/@kamsiob",
        "https://github.com/kamsiob",
        "https://kamsiob.com",
        "https://buymeacoffee.com/kamsiob",
        "https://t.me/+g5LKm9rUnNcxMjk5",
        "mailto:hello@kamsiob.com",
    ]
    assert [name for name, _d, _u in LINKS][3] == "Buy Me a Coffee"
    session.close()


# ---------- the standing promise ----------


def test_dig_makes_no_network_calls(profile, qtbot):
    """The one claim the whole app rests on."""
    import socket

    session = Session(profile, qtbot)

    def refuse(*args, **kwargs):
        raise AssertionError("Dig tried to open a socket")

    original_socket = socket.socket
    original_create = socket.create_connection
    socket.socket = refuse  # type: ignore[assignment]
    socket.create_connection = refuse  # type: ignore[assignment]
    try:
        session.store.create_idea("An idea\nwith a note")
        for n in range(4):
            session.store.create_idea(f"Filler {n}")
        for key, _label, _hint in SCREENS:
            session.window.go_to(key)
            session.screen(key).refresh()
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_create  # type: ignore[assignment]

    session.close()
