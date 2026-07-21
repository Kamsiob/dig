"""Ideas screen, idea editor, and the promote flow."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from dig.storage import Store
from dig.theme import LIGHT_MODE, ThemeManager
from dig.ui.window import MainWindow


@pytest.fixture
def window(qtbot, store: Store):
    w = MainWindow(store, ThemeManager(LIGHT_MODE))
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    return w


@pytest.fixture
def always_confirm(monkeypatch):
    """Answer every confirm dialog with yes, without showing it."""
    monkeypatch.setattr(
        "dig.ui.dialogs.ConfirmDialog.ask",
        staticmethod(lambda *a, **k: True),
    )


@pytest.fixture
def never_confirm(monkeypatch):
    monkeypatch.setattr(
        "dig.ui.dialogs.ConfirmDialog.ask",
        staticmethod(lambda *a, **k: False),
    )


# ---------- ideas screen ----------


def test_ideas_lists_everything_newest_first(window, store: Store):
    for n in range(5):
        store.create_idea(f"Idea {n}")
    window.go_to("ideas")
    screen = window.screens["ideas"]

    assert [r.idea.title for r in screen._rows] == [
        "Idea 4",
        "Idea 3",
        "Idea 2",
        "Idea 1",
        "Idea 0",
    ]


def test_ideas_empty_state(window, store: Store):
    window.go_to("ideas")
    screen = window.screens["ideas"]
    assert screen.empty.isVisible()
    assert screen.empty.text() == "Nothing buried yet. Jot the first one on Home."


def test_search_filters_title_and_note(window, qtbot, store: Store):
    store.create_idea("Clipboard tool\nexpires after a day")
    store.create_idea("RSS digest\nposts to telegram")
    window.go_to("ideas")
    screen = window.screens["ideas"]

    screen.search.setText("clipboard")
    assert [r.idea.title for r in screen._rows] == ["Clipboard tool"]

    screen.search.setText("telegram")
    assert [r.idea.title for r in screen._rows] == ["RSS digest"]

    screen.search.setText("zzz")
    assert screen._rows == []
    assert screen.empty.isVisible()
    assert screen.empty.text() == "Nothing matches that."


def test_escape_clears_the_search(window, qtbot, store: Store):
    store.create_idea("Findable")
    window.go_to("ideas")
    screen = window.screens["ideas"]
    screen.search.setText("zzz")
    assert screen._rows == []

    screen.search.setFocus()
    qtbot.keyClick(screen.search, Qt.Key.Key_Escape)

    assert screen.search.text() == ""
    assert [r.idea.title for r in screen._rows] == ["Findable"]


def test_promoted_ideas_are_hidden_then_shown_dimmed(window, store: Store):
    kept = store.create_idea("Still an idea")
    promoted = store.create_idea("Became an app")
    assert kept is not None and promoted is not None
    store.promote_idea(promoted.id, "Local AI Hub")

    window.go_to("ideas")
    screen = window.screens["ideas"]
    assert screen.show_promoted.isChecked() is False
    assert [r.idea.title for r in screen._rows] == ["Still an idea"]

    screen.show_promoted.setChecked(True)
    titles = [r.idea.title for r in screen._rows]
    assert "Became an app" in titles

    row = next(r for r in screen._rows if r.idea.title == "Became an app")
    assert row._read_only, "a promoted idea is history, not editable here"
    assert row.promote is None
    assert row.suffix.text() == "→ Local AI Hub"


def test_deleting_from_the_ledger_asks_first(window, store: Store, never_confirm):
    idea = store.create_idea("Do not delete me")
    assert idea is not None
    window.go_to("ideas")
    screen = window.screens["ideas"]

    screen._delete(idea.id)

    assert store.get_idea(idea.id) is not None, "cancelling must change nothing"


def test_deleting_from_the_ledger(window, store: Store, always_confirm):
    idea = store.create_idea("Delete me")
    assert idea is not None
    window.go_to("ideas")
    screen = window.screens["ideas"]

    screen._delete(idea.id)

    assert store.get_idea(idea.id) is None
    assert screen._rows == []


# ---------- idea editor ----------


def test_opening_an_idea_loads_it(window, store: Store):
    idea = store.create_idea("Pocket wiki\none file per video")
    assert idea is not None

    window.open_idea(idea.id)

    assert window.current_screen_key == "idea_editor"
    editor = window.screens["idea_editor"]
    assert editor.title_field.text() == "Pocket wiki"
    assert editor.note_field.toPlainText() == "one file per video"
    assert "never opened since" in editor.meta.text()


def test_the_rail_keeps_ideas_lit_while_editing(window, store: Store):
    idea = store.create_idea("Anything")
    assert idea is not None
    window.open_idea(idea.id)

    assert window.rail.nav_items["ideas"].property("active") is True


def test_edits_save_themselves(window, qtbot, store: Store):
    idea = store.create_idea("Old title\nold note")
    assert idea is not None
    window.open_idea(idea.id)
    editor = window.screens["idea_editor"]

    editor.title_field.setText("New title")
    editor.title_field.textEdited.emit("New title")
    editor.note_field.setPlainText("new note")
    qtbot.waitUntil(
        lambda: (store.get_idea(idea.id).title == "New title"), timeout=3000
    )

    saved = store.get_idea(idea.id)
    assert saved is not None
    assert saved.title == "New title"
    assert saved.note == "new note"


def test_navigating_away_saves_what_was_typed(window, store: Store):
    idea = store.create_idea("Before")
    assert idea is not None
    window.open_idea(idea.id)
    editor = window.screens["idea_editor"]

    editor.title_field.setText("After")
    editor.title_field.textEdited.emit("After")
    window.go_to("ideas")  # leave before the debounce fires

    saved = store.get_idea(idea.id)
    assert saved is not None and saved.title == "After"


def test_deleting_from_the_editor_returns_to_the_ledger(
    window, store: Store, always_confirm
):
    idea = store.create_idea("Delete from editor")
    assert idea is not None
    window.open_idea(idea.id)

    window.screens["idea_editor"]._delete()

    assert store.get_idea(idea.id) is None
    assert window.current_screen_key == "ideas"


def test_editor_delete_can_be_cancelled(window, store: Store, never_confirm):
    idea = store.create_idea("Survives")
    assert idea is not None
    window.open_idea(idea.id)

    window.screens["idea_editor"]._delete()

    assert store.get_idea(idea.id) is not None
    assert window.current_screen_key == "idea_editor"


def test_the_confirm_dialog_defaults_to_keeping(qtbot):
    from PySide6.QtWidgets import QLabel

    from dig.theme import LIGHT
    from dig.ui.dialogs import ConfirmDialog

    question = "Bury it for good? This can't be undug."
    dialog = ConfirmDialog(LIGHT, question, "Bury it")
    qtbot.addWidget(dialog)

    assert dialog.cancel_button.isDefault(), "Enter must not destroy anything"
    assert dialog.cancel_button.text() == "Keep it"
    assert dialog.confirm_button.text() == "Bury it"

    shown = [label.text() for label in dialog.findChildren(QLabel)]
    assert question in shown, "the dialog must state exactly what will happen"


# ---------- promote ----------


def test_promote_prefills_the_app_editor(window, store: Store):
    idea = store.create_idea("Pocket wiki\none markdown file per video")
    assert idea is not None

    window.promote_idea(idea.id)

    assert window.current_screen_key == "app_editor"
    editor = window.screens["app_editor"]
    assert editor.name_field.text() == "Pocket wiki"
    assert editor.description_field.toPlainText() == "one markdown file per video"
    assert editor.origin_idea is not None and editor.origin_idea.id == idea.id


def test_creating_the_app_links_it_to_the_idea(window, store: Store):
    idea = store.create_idea("Pocket wiki\none file per video")
    assert idea is not None
    window.promote_idea(idea.id)
    editor = window.screens["app_editor"]
    editor.github_field.setText("https://github.com/kamsiob/pocket-wiki")
    editor.shipped_box.setChecked(True)

    editor.create_button.click()

    apps = store.list_apps()
    assert len(apps) == 1
    app = apps[0]
    assert app.name == "Pocket wiki"
    assert app.description == "one file per video"
    assert app.github_url == "https://github.com/kamsiob/pocket-wiki"
    assert app.shipped is True
    assert app.origin_idea_id == idea.id

    linked = store.get_idea(idea.id)
    assert linked is not None and linked.promoted_app_id == app.id


def test_a_promoted_idea_leaves_the_pools_but_survives(window, store: Store):
    idea = store.create_idea("Becomes an app")
    assert idea is not None
    window.promote_idea(idea.id)
    window.screens["app_editor"].create_button.click()

    assert store.list_ideas() == []
    window.go_to("ideas")
    screen = window.screens["ideas"]
    assert screen._rows == []

    screen.show_promoted.setChecked(True)
    assert [r.idea.title for r in screen._rows] == ["Becomes an app"]


def test_cancelling_promote_changes_nothing(window, store: Store):
    idea = store.create_idea("Stays an idea")
    assert idea is not None
    window.promote_idea(idea.id)

    window.screens["app_editor"].cancelled.emit()

    assert store.list_apps() == []
    still = store.get_idea(idea.id)
    assert still is not None and not still.is_promoted


def test_an_app_needs_a_name_before_it_can_be_created(window, store: Store):
    window.new_app()
    editor = window.screens["app_editor"]

    assert editor.name_field.text() == ""
    assert not editor.create_button.isEnabled()

    editor.name_field.setText("Bearings")
    assert editor.create_button.isEnabled()

    editor.name_field.setText("   ")
    assert not editor.create_button.isEnabled()


def test_new_app_starts_blank_after_a_promote(window, store: Store):
    """The editor is reused, so it must not leak the last idea into a new app."""
    idea = store.create_idea("Promoted one\nwith a note")
    assert idea is not None
    window.promote_idea(idea.id)
    assert window.screens["app_editor"].name_field.text() == "Promoted one"

    window.new_app()
    editor = window.screens["app_editor"]

    assert editor.name_field.text() == ""
    assert editor.description_field.toPlainText() == ""
    assert editor.origin_idea is None


def test_an_app_added_directly_has_no_origin(window, store: Store):
    window.new_app()
    editor = window.screens["app_editor"]
    editor.name_field.setText("Bearings")
    editor.create_button.click()

    app = store.list_apps()[0]
    assert app.origin_idea_id is None
    assert not app.was_dug_from_an_idea
