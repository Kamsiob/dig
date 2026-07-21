"""Home tests: jot capture, Recent, and the Unearthed draw."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtCore import Qt

from dig import timefmt
from dig.screens.home import HomeScreen
from dig.storage import Store
from dig.theme import LIGHT, LIGHT_MODE, ThemeManager
from dig.ui.window import MainWindow


@pytest.fixture
def home(qtbot, store: Store):
    window = MainWindow(store, ThemeManager(LIGHT_MODE))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    window.go_to("home")
    return window.screens["home"]


def jot(home: HomeScreen, qtbot, text: str) -> None:
    """Type into the jot field and press Enter, as a person would."""
    home.jot.field.setFocus()
    qtbot.keyClicks(home.jot.field, text)
    qtbot.keyClick(home.jot.field, Qt.Key.Key_Return)


# ---------- relative time ----------


@pytest.mark.parametrize(
    "delta, expected",
    [
        (timedelta(seconds=5), "just now"),
        (timedelta(minutes=12), "12m ago"),
        (timedelta(hours=2), "2h ago"),
        (timedelta(days=2), "2d ago"),
        (timedelta(days=5), "5d ago"),
        (timedelta(days=8), "1w ago"),
        (timedelta(weeks=6), "6 weeks"),
    ],
)
def test_relative_phrasing(delta, expected):
    now = datetime.now(timezone.utc)
    stamp = (now - delta).isoformat(timespec="seconds")
    assert timefmt.relative(stamp, now) == expected


def test_relative_becomes_a_date_past_two_months():
    now = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
    stamp = (now - timedelta(weeks=12)).isoformat(timespec="seconds")
    assert timefmt.relative(stamp, now) == timefmt.on_date(stamp, now)
    assert "ago" not in timefmt.relative(stamp, now)


def test_buried_duration_reads_naturally():
    now = datetime.now(timezone.utc)
    six_weeks = (now - timedelta(weeks=6)).isoformat(timespec="seconds")
    one_week = (now - timedelta(weeks=1)).isoformat(timespec="seconds")
    assert timefmt.buried(six_weeks, now) == "buried 6 weeks"
    assert timefmt.buried(one_week, now) == "buried 1 week"


def test_unreadable_timestamps_never_crash():
    assert timefmt.relative("not a timestamp") == ""
    assert timefmt.relative(None) == ""
    assert timefmt.buried("") == ""


# ---------- jot ----------


def test_focus_is_in_the_jot_field_when_home_opens(home, qtbot):
    qtbot.waitUntil(lambda: home.jot.field.hasFocus())


def test_enter_keeps_the_idea_and_clears_the_field(home, qtbot, store: Store):
    jot(home, qtbot, "Clipboard history that expires")

    assert home.jot.field.toPlainText() == ""
    assert home.jot.field.hasFocus(), "focus stays put, ready for the next one"
    ideas = store.list_ideas()
    assert len(ideas) == 1
    assert ideas[0].title == "Clipboard history that expires"


def test_first_line_is_the_title_and_the_rest_is_the_note(home, qtbot, store: Store):
    home.jot.field.setFocus()
    qtbot.keyClicks(home.jot.field, "Pocket wiki")
    qtbot.keyClick(home.jot.field, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    qtbot.keyClicks(home.jot.field, "one markdown file per video")
    qtbot.keyClick(home.jot.field, Qt.Key.Key_Return)

    idea = store.list_ideas()[0]
    assert idea.title == "Pocket wiki"
    assert idea.note == "one markdown file per video"


def test_shift_enter_makes_a_new_line_and_keeps_nothing(home, qtbot, store: Store):
    home.jot.field.setFocus()
    qtbot.keyClicks(home.jot.field, "First line")
    qtbot.keyClick(home.jot.field, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)

    assert store.list_ideas() == [], "Shift+Enter must not save"
    assert "\n" in home.jot.field.toPlainText()


def test_empty_enter_does_nothing_quietly(home, qtbot, store: Store):
    home.jot.field.setFocus()
    qtbot.keyClick(home.jot.field, Qt.Key.Key_Return)
    qtbot.keyClicks(home.jot.field, "   ")
    qtbot.keyClick(home.jot.field, Qt.Key.Key_Return)

    assert store.list_ideas() == []
    assert home.recent_empty.isVisible()


def test_a_kept_idea_appears_at_the_top_of_recent(home, qtbot, store: Store):
    jot(home, qtbot, "First one")
    jot(home, qtbot, "Second one")

    titles = [row.idea.title for row in home._rows]
    assert titles[0] == "Second one"
    assert titles[1] == "First one"


def test_the_keep_button_does_what_enter_does(home, qtbot, store: Store):
    home.jot.field.setPlainText("Kept by the button")
    home.jot.keep_button.click()

    assert [i.title for i in store.list_ideas()] == ["Kept by the button"]
    assert home.jot.field.toPlainText() == ""


# ---------- recent ----------


def test_recent_shows_exactly_three(home, qtbot, store: Store):
    for n in range(6):
        store.create_idea(f"Idea {n}")
    home.refresh()

    assert len(home._rows) == 3
    assert [r.idea.title for r in home._rows] == ["Idea 5", "Idea 4", "Idea 3"]


def test_recent_hides_promoted_ideas(home, store: Store):
    keep = store.create_idea("Stays an idea")
    gone = store.create_idea("Becomes an app")
    assert keep is not None and gone is not None
    store.promote_idea(gone.id, "Becomes an app")
    home.refresh()

    assert [r.idea.title for r in home._rows] == ["Stays an idea"]


def test_recent_empty_state(home, store: Store):
    home.refresh()
    assert home.recent_empty.isVisible()
    assert home.recent_empty.text() == "Nothing buried yet. Jot the first one above."


def test_row_actions_appear_on_focus(home, qtbot, store: Store):
    """Promote stays out of the way until the row is hovered or focused."""
    store.create_idea("Hover me\nwith a note")
    home.refresh()
    row = home._rows[0]
    qtbot.waitUntil(row.isVisible)  # a widget cannot take focus before it shows

    assert row.promote is not None
    assert row.promote.isHidden()

    row.setFocus()
    assert row.hasFocus()
    assert not row.promote.isHidden()

    row.clearFocus()
    assert row.promote.isHidden()


# ---------- unearthed ----------


def test_unearthed_is_empty_below_four_ideas(home, store: Store):
    for n in range(3):
        store.create_idea(f"Idea {n}")
    home.on_shown()

    assert home.unearthed.idea is None
    assert not home.unearthed.open_button.isVisible()
    assert not home.unearthed.again_button.isVisible()
    assert "Nothing old enough to unearth yet." in home.unearthed.title.text()
    assert home.unearthed.strata.isVisible(), "the gauge stays"


def test_unearthed_draws_from_below_the_recent_three(home, store: Store):
    for n in range(7):
        store.create_idea(f"Idea {n}")
    recent = {i.title for i in store.recent_ideas()}

    for _ in range(25):
        home.on_shown()
        assert home.unearthed.idea is not None
        assert home.unearthed.idea.title not in recent


def test_dig_again_never_repeats_the_shown_idea(home, store: Store):
    for n in range(8):
        store.create_idea(f"Idea {n}")
    home.on_shown()

    for _ in range(30):
        before = home.unearthed.idea.id
        home.dig_again()
        assert home.unearthed.idea.id != before


def test_dig_again_on_a_pool_of_one_is_a_quiet_no_op(home, store: Store):
    for n in range(4):
        store.create_idea(f"Idea {n}")
    home.on_shown()
    only = home.unearthed.idea
    assert only is not None

    home.dig_again()
    assert home.unearthed.idea is not None
    assert home.unearthed.idea.id == only.id


def test_the_draw_reaches_every_buried_idea(home, store: Store):
    for n in range(9):
        store.create_idea(f"Idea {n}")
    expected = {i.id for i in store.unearth_candidates()}

    seen = set()
    for _ in range(120):
        home.on_shown()
        seen.add(home.unearthed.idea.id)
    assert seen == expected


def test_opening_an_unearthed_idea_stamps_it(home, store: Store, qtbot):
    for n in range(6):
        store.create_idea(f"Idea {n}")
    home.on_shown()
    shown = home.unearthed.idea
    assert shown is not None and shown.never_opened

    opened: list[int] = []
    home.idea_opened.connect(opened.append)
    home.unearthed.open_button.click()

    assert opened == [shown.id]
    refreshed = store.get_idea(shown.id)
    assert refreshed is not None and not refreshed.never_opened


def test_never_opened_since_is_shown_then_gone(home, store: Store):
    for n in range(6):
        store.create_idea(f"Idea {n}")
    home.on_shown()
    shown = home.unearthed.idea
    assert shown is not None
    assert "never opened since" in home.unearthed.meta.text()

    store.mark_idea_opened(shown.id)
    home.unearthed.show_idea(store.get_idea(shown.id))
    assert "never opened since" not in home.unearthed.meta.text()
    assert "jotted" in home.unearthed.meta.text()


def test_the_unearthed_tag_says_how_long_it_was_buried(home, store: Store):
    for n in range(6):
        store.create_idea(f"Idea {n}")
    home.on_shown()
    assert home.unearthed.tag.text().startswith("UNEARTHED · BURIED ")


def test_a_long_gist_is_never_clipped(home, qtbot, store: Store):
    """Wrapped text must reserve the height it paints in.

    A plain wrapped QLabel reports a height from a width the layout has not
    settled yet, and the overflow lands on top of the meta row below it.
    """
    from PySide6.QtCore import Qt as _Qt

    long_note = (
        "One markdown file per video: gear used, commands run, links mentioned. "
        "Searchable. Becomes the description generator later, and eventually "
        "the source for chapter markers as well."
    )
    for n in range(6):
        store.create_idea(f"Idea {n}\n{long_note}")
    home.on_shown()
    qtbot.waitUntil(lambda: home.unearthed.gist.width() > 0)

    gist = home.unearthed.gist
    needed = gist.fontMetrics().boundingRect(
        0, 0, gist.width(), 10_000, _Qt.TextFlag.TextWordWrap, gist.text()
    ).height()

    assert gist.height() >= needed, "the gist is painting outside its own space"
    assert gist.y() + gist.height() <= home.unearthed.meta.y(), "gist overlaps meta"


# ---------- motion ----------


def test_the_highlight_is_skipped_under_reduced_motion(
    home, qtbot, store: Store, monkeypatch
):
    monkeypatch.setattr("dig.screens.home.prefers_reduced_motion", lambda: True)
    jot(home, qtbot, "Kept without a flash")

    row = home._rows[0]
    assert row.styleSheet() == "", "no highlight wash under reduced motion"
