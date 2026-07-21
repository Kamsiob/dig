"""Settings, the About dialog, and the desktop integration files."""

from __future__ import annotations

import re
import stat
from pathlib import Path

import pytest

from dig import paths
from dig.storage import Store
from dig.theme import DARK_MODE, LIGHT_MODE, SYSTEM_MODE, ThemeManager
from dig.ui.about import LINKS, AboutDialog
from dig.ui.window import MainWindow

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def window(qtbot, store: Store):
    w = MainWindow(store, ThemeManager(LIGHT_MODE))
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    return w


# ---------- settings ----------


def test_settings_shows_the_data_folder(window):
    window.go_to("settings")
    screen = window.screens["settings"]
    assert screen.folder_path.text() == str(paths.data_dir())


def test_the_two_appearance_controls_stay_in_step(window):
    window.go_to("settings")
    settings = window.screens["settings"]

    settings.segmented.picked.emit(DARK_MODE)
    assert window.theme.mode == DARK_MODE
    assert window.rail.segmented._buttons[DARK_MODE].property("active") is True
    assert settings.segmented._buttons[DARK_MODE].property("active") is True

    window.rail.appearance_picked.emit(SYSTEM_MODE)
    assert settings.segmented._buttons[SYSTEM_MODE].property("active") is True
    assert window.rail.segmented._buttons[SYSTEM_MODE].property("active") is True


def test_settings_holds_only_appearance_and_the_data_folder(window):
    """Nothing else in v1. No account, no sync, no toggles that do nothing."""
    from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit

    window.go_to("settings")
    screen = window.screens["settings"]

    assert screen.findChildren(QCheckBox) == []
    assert screen.findChildren(QComboBox) == []
    assert screen.findChildren(QLineEdit) == []

    from PySide6.QtWidgets import QPushButton

    buttons = [b.text() for b in screen.findChildren(QPushButton)]
    # The three appearance segments, and the one way to reach the folder.
    assert sorted(buttons) == ["Dark", "Light", "Open folder", "System"]


# ---------- about ----------


def test_about_lists_every_link(qtbot):
    from dig.theme import LIGHT

    dialog = AboutDialog(LIGHT)
    qtbot.addWidget(dialog)

    urls = [button.property("url") for button in dialog.link_buttons]
    assert urls == [
        "https://youtube.com/@kamsiob",
        "https://github.com/kamsiob",
        "https://kamsiob.com",
        "https://buymeacoffee.com/kamsiob",
        "https://t.me/+g5LKm9rUnNcxMjk5",
        "mailto:hello@kamsiob.com",
    ]


def test_about_opens_each_link_with_the_desktop(qtbot, monkeypatch):
    from dig.theme import LIGHT

    opened: list[str] = []
    monkeypatch.setattr("dig.ui.about.open_link", lambda url: opened.append(url) or True)

    dialog = AboutDialog(LIGHT)
    qtbot.addWidget(dialog)
    for button in dialog.link_buttons:
        button.click()

    assert opened == [url for _name, _detail, url in LINKS]


def test_about_states_the_licence_and_the_promise(qtbot):
    from PySide6.QtWidgets import QLabel

    from dig.theme import LIGHT

    dialog = AboutDialog(LIGHT)
    qtbot.addWidget(dialog)
    words = " ".join(label.text() for label in dialog.findChildren(QLabel))

    assert "A place to bury ideas and dig them back up." in words
    assert "AGPLv3" in words
    assert "Everything stays on your machine." in words


def test_the_rail_trigger_opens_about(window, monkeypatch):
    shown: list[int] = []
    monkeypatch.setattr(AboutDialog, "exec", lambda _self: shown.append(1) or 0)
    window.rail.about.click()
    assert shown == [1]


# ---------- desktop integration ----------


def test_the_desktop_entry_is_well_formed():
    entry = (ROOT / "packaging" / "dig.desktop").read_text()
    assert entry.startswith("[Desktop Entry]")
    assert "Name=Dig" in entry
    assert "Icon=dig" in entry
    assert "Type=Application" in entry
    # KDE on Wayland groups the window with the launcher through this.
    assert "StartupWMClass=dig" in entry


def test_the_app_announces_its_desktop_file():
    """Without this, Plasma on Wayland shows a generic icon for the window."""
    source = (ROOT / "dig" / "app.py").read_text()
    assert 'setDesktopFileName("dig")' in source or "setDesktopFileName(DESKTOP_FILE_NAME)" in source


def test_every_icon_size_exists():
    icons = ROOT / "assets" / "icons"
    assert (icons / "dig.svg").is_file()
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        png = icons / f"dig-{size}.png"
        assert png.is_file(), f"missing {png.name}"
        assert png.stat().st_size > 0


def test_the_installers_are_executable_and_user_level():
    for name in ("install.sh", "uninstall.sh"):
        script = ROOT / name
        assert script.is_file()
        assert script.stat().st_mode & stat.S_IXUSR, f"{name} must be executable"

        # Comments explain what the script avoids, so only real code is checked.
        body = "\n".join(
            line for line in script.read_text().splitlines()
            if not line.lstrip().startswith("#")
        )
        # Bazzite's /usr is immutable: nothing may be written there, and
        # nothing may create users or ask for root.
        assert not re.search(r"(?<!\w)/usr/(?!bin/env)", body), f"{name} writes to /usr"
        assert "useradd" not in body
        assert "sudo " not in body
        assert "$HOME" in body or "XDG_DATA_HOME" in body


def test_uninstall_leaves_the_data_alone():
    body = (ROOT / "uninstall.sh").read_text()
    assert "rm -rf \"$DATA_DIR\"" not in body
    assert "left alone" in body


def test_install_never_writes_outside_home():
    body = (ROOT / "install.sh").read_text()
    for forbidden in ("/etc/", "/opt/", "/var/lib/"):
        assert forbidden not in body
