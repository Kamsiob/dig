"""Shell tests: fonts, both palettes, navigation, keyboard, geometry memory."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QLineEdit

from dig.storage import Store
from dig.theme import (
    APPEARANCE_KEY,
    DARK,
    DARK_MODE,
    LIGHT,
    LIGHT_MODE,
    SYSTEM_MODE,
    ThemeManager,
)
from dig.theme import fonts as theme_fonts
from dig.ui.rail import SCREENS
from dig.ui.window import GEOMETRY_KEY, MIN_HEIGHT, MIN_WIDTH, MainWindow


@pytest.fixture
def window(qtbot, store: Store):
    theme = ThemeManager(LIGHT_MODE)
    theme.apply()
    w = MainWindow(store, theme)
    qtbot.addWidget(w)
    w.resize(1080, 720)
    w.show()
    qtbot.waitExposed(w)
    return w


# ---------- fonts ----------


def test_bundled_fonts_all_load(qapp):
    theme_fonts.register_fonts()
    assert theme_fonts.missing_font_files() == []
    assert theme_fonts.serif() == "Fraunces"
    assert theme_fonts.sans() == "IBM Plex Sans"
    assert theme_fonts.mono() == "IBM Plex Mono"


def test_serif_has_real_distinct_weights(qapp):
    """Fraunces must ship as separate weights.

    Loaded as a variable font, Qt would take its default axis position, which
    for Fraunces is Black at the smallest optical size, and never vary it.
    """
    theme_fonts.register_fonts()
    styles = set(QFontDatabase.styles("Fraunces"))
    assert {"Regular", "SemiBold", "Bold"} <= styles

    sans_styles = set(QFontDatabase.styles("IBM Plex Sans"))
    assert {"Regular", "Medium", "SemiBold"} <= sans_styles


def test_no_os_default_font_for_visible_text(window):
    """Every visible label resolves to one of the three bundled families."""
    from PySide6.QtWidgets import QLabel

    allowed = {"Fraunces", "IBM Plex Sans", "IBM Plex Mono"}
    checked = 0
    for label in window.findChildren(QLabel):
        if not label.text().strip():
            continue
        family = label.fontInfo().family()
        assert family in allowed, f"{label.text()!r} fell back to {family}"
        checked += 1
    assert checked > 0


# ---------- palettes ----------


def test_both_palettes_carry_the_same_tokens():
    assert set(vars(LIGHT)) == set(vars(DARK))
    assert LIGHT.is_dark is False and DARK.is_dark is True


def test_no_banned_colours_in_either_palette():
    """No purple, indigo or violet anywhere. It is the fingerprint being avoided."""
    for palette in (LIGHT, DARK):
        for name, value in vars(palette).items():
            if not isinstance(value, str) or not value.startswith("#"):
                continue
            r = int(value[1:3], 16)
            g = int(value[3:5], 16)
            b = int(value[5:7], 16)
            # Purple reads as blue and red both clearly ahead of green.
            purple = b > g + 24 and r > g + 8
            assert not purple, f"{palette.name}.{name} = {value} looks purple"


def test_stylesheet_has_no_gradients_or_rounded_corners(qapp):
    from dig.theme import qss

    for palette in (LIGHT, DARK):
        sheet = qss.build(palette)
        assert "gradient" not in sheet.lower()
        # Every radius declared must be zero.
        for chunk in sheet.split("border-radius:")[1:]:
            assert chunk.strip().startswith("0"), "corners are square everywhere"


def test_theme_modes_resolve(qapp):
    theme = ThemeManager(LIGHT_MODE)
    assert theme.is_dark is False and theme.palette is LIGHT

    theme.set_mode(DARK_MODE)
    assert theme.is_dark is True and theme.palette is DARK

    theme.set_mode(SYSTEM_MODE)
    assert theme.mode == SYSTEM_MODE
    assert theme.is_dark == ThemeManager.system_is_dark()


def test_system_mode_follows_a_scheme_change(qapp, monkeypatch):
    theme = ThemeManager(SYSTEM_MODE)
    seen: list[bool] = []
    theme.changed.connect(lambda: seen.append(theme.is_dark))

    monkeypatch.setattr(ThemeManager, "system_is_dark", staticmethod(lambda: True))
    theme._on_system_scheme_changed()
    assert seen == [True]
    assert theme.palette is DARK

    monkeypatch.setattr(ThemeManager, "system_is_dark", staticmethod(lambda: False))
    theme._on_system_scheme_changed()
    assert seen == [True, False]
    assert theme.palette is LIGHT


def test_a_fixed_mode_ignores_the_system_scheme(qapp, monkeypatch):
    theme = ThemeManager(LIGHT_MODE)
    fired: list[int] = []
    theme.changed.connect(lambda: fired.append(1))

    monkeypatch.setattr(ThemeManager, "system_is_dark", staticmethod(lambda: True))
    theme._on_system_scheme_changed()

    assert fired == [], "Light mode must not follow the desktop"
    assert theme.palette is LIGHT


def test_appearance_choice_is_remembered(window, store: Store):
    window.set_appearance(DARK_MODE)
    assert store.get_setting(APPEARANCE_KEY) == DARK_MODE
    assert window.theme.palette is DARK

    window.set_appearance(SYSTEM_MODE)
    assert store.get_setting(APPEARANCE_KEY) == SYSTEM_MODE


def test_rail_and_theme_stay_in_step(window):
    window.set_appearance(DARK_MODE)
    segments = window.rail.segmented._buttons
    assert segments[DARK_MODE].property("active") is True
    assert segments[LIGHT_MODE].property("active") is False


# ---------- navigation ----------


def test_every_screen_is_reachable(window):
    for key, _label, _hint in SCREENS:
        window.go_to(key)
        assert window.current_screen_key == key
        assert window.stack.currentWidget() is window.screens[key]
        assert window.rail.nav_items[key].property("active") is True


def test_number_keys_switch_screens(window, qtbot):
    for index, (key, _label, _hint) in enumerate(SCREENS):
        qtbot.keyClick(window, getattr(Qt.Key, f"Key_{index + 1}"))
        assert window.current_screen_key == key


def test_number_keys_are_ignored_while_typing(window, qtbot):
    window.go_to("home")
    field = QLineEdit(window)
    field.show()
    field.setFocus()
    qtbot.waitUntil(lambda: field.hasFocus())

    qtbot.keyClick(field, Qt.Key.Key_3)

    assert window.current_screen_key == "home", "typing must not navigate"
    assert field.text() == "3"


def test_the_map_shows_on_home_only(window):
    window.go_to("home")
    assert window.map_backdrop.isVisible()
    for key in ("ideas", "apps", "export", "settings"):
        window.go_to(key)
        assert not window.map_backdrop.isVisible(), f"no map on {key}"


def test_grain_and_map_never_take_a_click(window):
    for overlay in (window.grain, window.map_backdrop):
        assert overlay.testAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )


# ---------- window ----------


def test_minimum_size_holds_the_layout(window):
    assert window.minimumWidth() == MIN_WIDTH
    assert window.minimumHeight() == MIN_HEIGHT
    window.resize(MIN_WIDTH, MIN_HEIGHT)
    assert window.rail.width() == 216


def test_geometry_is_remembered_across_a_restart(qtbot, store: Store):
    """The window comes back the size it was left.

    Only the height is asserted. Qt deliberately clamps a restored geometry to
    the screen it will appear on, and the offscreen screen these tests run
    against is narrower than Dig's own 980px minimum, so the restored width is
    pinned to that minimum here regardless of what was saved.
    """
    from PySide6.QtGui import QGuiApplication

    available = QGuiApplication.primaryScreen().availableGeometry()
    target_height = min(720, available.height() - 40)

    first = MainWindow(store, ThemeManager(LIGHT_MODE))
    qtbot.addWidget(first)
    first.show()
    qtbot.waitExposed(first)
    first.resize(first.width(), target_height)
    qtbot.waitUntil(lambda: first.height() == target_height)
    first._save_geometry()
    first.close()

    assert store.get_setting(GEOMETRY_KEY, "") != "", "geometry must be written"

    second = MainWindow(store, ThemeManager(LIGHT_MODE))
    qtbot.addWidget(second)
    second.show()
    qtbot.waitExposed(second)
    assert second.height() == target_height


def test_a_fresh_profile_opens_at_a_sensible_size(qtbot, store: Store):
    """With nothing remembered, the window opens larger than the minimum."""
    assert store.get_setting(GEOMETRY_KEY, "") == ""
    window = MainWindow(store, ThemeManager(LIGHT_MODE))
    qtbot.addWidget(window)
    assert window.width() >= MIN_WIDTH
    assert window.height() >= MIN_HEIGHT


def test_a_recovery_notice_is_surfaced_plainly(window):
    assert not window.notice.isVisible()
    window.show_notice("Dig could not read its database, so it started a fresh one.")
    assert window.notice.isVisible()
    text = window.notice.message.text()
    assert "fresh one" in text
    for apology in ("sorry", "oops", "unfortunately", "!"):
        assert apology not in text.lower()
