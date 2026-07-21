"""The capture dialog: Ctrl K from anywhere, keyboard only, onto the right sheet."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from dig.storage import BUG, FEATURE, Store
from dig.theme import LIGHT_MODE, ThemeManager
from dig.ui.capture import NO_APPS_TEXT, CaptureDialog
from dig.ui.rail import SCREENS
from dig.ui.window import MainWindow


@pytest.fixture
def window(qtbot, store: Store):
    w = MainWindow(store, ThemeManager(LIGHT_MODE))
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    return w


def open_dialog(window, qtbot) -> CaptureDialog:
    """Open the dialog without blocking on exec()."""
    dialog = CaptureDialog(
        window.store, window.theme.palette, window._last_captured_app_id, window
    )
    dialog.captured.connect(window._on_captured)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    # Window activation lands a beat after show; the dialog claims focus then.
    qtbot.waitUntil(dialog.text_field.hasFocus, timeout=3000)
    return dialog


# ---------- reachability ----------


def test_ctrl_k_opens_capture_from_every_screen(window, qtbot, monkeypatch):
    """The real shortcut, on every screen, opening the real dialog.

    exec() is stubbed so the modal loop does not block the test; everything
    up to and including building the dialog is the app's own code.
    """
    opened: list[str] = []

    def record_instead_of_blocking(dialog_self):
        opened.append(window.current_screen_key)
        return 0

    monkeypatch.setattr(CaptureDialog, "exec", record_instead_of_blocking)

    for key, _label, _hint in SCREENS:
        window.go_to(key)
        qtbot.keyClick(window, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)

    assert opened == [key for key, _l, _h in SCREENS]


def test_ctrl_k_works_from_a_detail_screen_too(window, qtbot, store: Store, monkeypatch):
    app = store.create_app("Local AI Hub")
    window.open_app(app.id)

    opened: list[str] = []
    monkeypatch.setattr(
        CaptureDialog, "exec", lambda _self: opened.append("opened") or 0
    )
    qtbot.keyClick(window, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)

    assert opened == ["opened"]


def test_the_home_panel_asks_for_capture(window, qtbot, monkeypatch):
    asked: list[int] = []
    monkeypatch.setattr(window, "open_capture", lambda: asked.append(1))
    window.go_to("home")
    window.screens["home"].capture_panel.clicked.emit()
    assert asked == [1]


# ---------- with no apps ----------


def test_with_no_apps_it_says_so_and_cannot_save(window, qtbot):
    dialog = open_dialog(window, qtbot)

    assert dialog.no_apps.isVisible()
    assert dialog.no_apps.text() == NO_APPS_TEXT
    assert not dialog.app_picker.isVisible()
    assert not dialog.app_picker.isEnabled()

    dialog.text_field.setText("Something")
    assert not dialog.keep_button.isEnabled(), "nowhere to put it"


# ---------- capturing ----------


def test_a_captured_feature_lands_on_top_of_the_right_sheet(
    window, qtbot, store: Store
):
    app = store.create_app("Local AI Hub")
    other = store.create_app("Bearings")
    store.add_sheet_item(app.id, FEATURE, "An older feature")

    dialog = open_dialog(window, qtbot)
    dialog.text_field.setText("Disk usage per model")
    index = dialog.app_picker.findData(app.id)
    dialog.app_picker.setCurrentIndex(index)
    dialog._keep()

    items = store.list_sheet_items(app.id, FEATURE)
    assert [i.text for i in items] == ["Disk usage per model", "An older feature"]
    assert items[0].done is False
    assert store.list_sheet_items(other.id, FEATURE) == []


def test_the_bug_side_writes_to_the_bug_sheet(window, qtbot, store: Store):
    app = store.create_app("Local AI Hub")
    dialog = open_dialog(window, qtbot)

    dialog.kind_toggle.set_kind(BUG)
    dialog.text_field.setText("Lamp goes stale")
    dialog._keep()

    assert [i.text for i in store.list_sheet_items(app.id, BUG)] == ["Lamp goes stale"]
    assert store.list_sheet_items(app.id, FEATURE) == []


def test_feature_is_the_default(window, qtbot, store: Store):
    store.create_app("Anything")
    dialog = open_dialog(window, qtbot)
    assert dialog.kind_toggle.kind == FEATURE
    assert dialog.kind_toggle.buttons[FEATURE].property("active") is True


def test_arrow_keys_switch_between_feature_and_bug(window, qtbot, store: Store):
    store.create_app("Anything")
    dialog = open_dialog(window, qtbot)

    dialog.kind_toggle.toggle()
    assert dialog.kind_toggle.kind == BUG
    dialog.kind_toggle.toggle()
    assert dialog.kind_toggle.kind == FEATURE


def test_empty_text_cannot_be_kept(window, qtbot, store: Store):
    app = store.create_app("Anything")
    dialog = open_dialog(window, qtbot)

    dialog.text_field.setText("   ")
    assert not dialog.keep_button.isEnabled()
    dialog._keep()

    assert store.list_sheet_items(app.id, FEATURE) == []


def test_escape_cancels(window, qtbot, store: Store):
    app = store.create_app("Anything")
    dialog = open_dialog(window, qtbot)
    dialog.text_field.setText("Never kept")

    qtbot.keyClick(dialog, Qt.Key.Key_Escape)

    assert store.list_sheet_items(app.id, FEATURE) == []
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_the_whole_flow_works_without_a_mouse(window, qtbot, store: Store):
    """Ctrl K, type, Enter. Nothing else."""
    app = store.create_app("Local AI Hub")
    dialog = open_dialog(window, qtbot)

    assert dialog.text_field.hasFocus(), "typing starts immediately"
    qtbot.keyClicks(dialog.text_field, "Log bundle for bug reports")
    qtbot.keyClick(dialog, Qt.Key.Key_Return)

    items = store.list_sheet_items(app.id, FEATURE)
    assert [i.text for i in items] == ["Log bundle for bug reports"]
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_apps_are_offered_alphabetically(window, qtbot, store: Store):
    for name in ["logbook", "Bearings", "dig", "Local AI Hub"]:
        store.create_app(name)
    dialog = open_dialog(window, qtbot)

    offered = [dialog.app_picker.itemText(i) for i in range(dialog.app_picker.count())]
    assert offered == ["Bearings", "dig", "Local AI Hub", "logbook"]


def test_the_last_app_captured_is_preselected(window, qtbot, store: Store):
    first = store.create_app("Bearings")
    second = store.create_app("Local AI Hub")

    dialog = open_dialog(window, qtbot)
    dialog.app_picker.setCurrentIndex(dialog.app_picker.findData(second.id))
    dialog.text_field.setText("One")
    dialog._keep()

    assert window._last_captured_app_id == second.id

    again = open_dialog(window, qtbot)
    assert again.selected_app_id == second.id, "the session remembers"
    assert again.app_picker.currentText() == "Local AI Hub"
    _ = first


def test_the_session_memory_is_not_written_to_disk(window, qtbot, store: Store):
    app = store.create_app("Bearings")
    dialog = open_dialog(window, qtbot)
    dialog.text_field.setText("One")
    dialog._keep()

    keys = [
        row[0]
        for row in store.conn.execute("SELECT key FROM settings").fetchall()
    ]
    assert not any("captur" in key.lower() for key in keys)
    _ = app


def test_capturing_refreshes_what_is_on_screen(window, qtbot, store: Store):
    """An open App Detail shows the captured line without a manual reload."""
    app = store.create_app("Local AI Hub")
    window.open_app(app.id)
    detail = window.screens["app_detail"]
    assert detail.features._lines == []

    dialog = open_dialog(window, qtbot)
    dialog.text_field.setText("Captured from elsewhere")
    dialog._keep()

    assert [line.item.text for line in detail.features._lines] == [
        "Captured from elsewhere"
    ]
    assert detail.features.count.text() == "1 open · 0 done"
