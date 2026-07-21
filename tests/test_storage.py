"""Data layer tests: schema, every CRUD path, promote, attachments, recovery."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from dig.storage import BUG, FEATURE, Store, StoreError, split_jot
from dig.storage.schema import SCHEMA_VERSION, SchemaTooNewError, read_schema_version


# ---------- schema ----------


def test_schema_is_created_and_versioned(store: Store):
    tables = {
        r[0]
        for r in store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert {"ideas", "apps", "sheet_items", "attachments", "settings"} <= tables
    assert read_schema_version(store.conn) == SCHEMA_VERSION


def test_wal_and_foreign_keys_are_on(store: Store):
    assert store.conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert store.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_migration_is_idempotent(data_dir: Path):
    db = data_dir / "dig.db"
    first = Store(db_file=db, attachments_root=data_dir / "a").open()
    first.create_idea("Survives a reopen")
    first.close()

    second = Store(db_file=db, attachments_root=data_dir / "a").open()
    assert len(second.list_ideas()) == 1
    assert read_schema_version(second.conn) == SCHEMA_VERSION
    second.close()


def test_sheet_kind_is_constrained(store: Store):
    app = store.create_app("Dig")
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "INSERT INTO sheet_items (app_id, kind, text, created_at) "
            "VALUES (?, 'chore', 'nope', '2026-01-01T00:00:00+00:00')",
            (app.id,),
        )


# ---------- jot splitting ----------


@pytest.mark.parametrize(
    "raw, title, note",
    [
        ("Just a title", "Just a title", ""),
        ("Title\nthe note", "Title", "the note"),
        ("Title\n\nnote after a blank", "Title", "note after a blank"),
        ("  padded  \n  body  ", "padded", "body"),
        ("Multi\nline one\nline two", "Multi", "line one\nline two"),
        ("", "", ""),
        ("   \n  \n ", "", ""),
    ],
)
def test_split_jot(raw: str, title: str, note: str):
    assert split_jot(raw) == (title, note)


# ---------- ideas ----------


def test_create_and_read_idea(store: Store):
    idea = store.create_idea("Clipboard history that expires\nauto-deletes after 24h")
    assert idea is not None
    assert idea.title == "Clipboard history that expires"
    assert idea.note == "auto-deletes after 24h"
    assert idea.last_opened_at is None
    assert idea.never_opened
    assert not idea.is_promoted
    assert store.get_idea(idea.id) == idea


def test_empty_jot_saves_nothing(store: Store):
    assert store.create_idea("") is None
    assert store.create_idea("   \n\t \n ") is None
    assert store.list_ideas() == []


def test_update_and_delete_idea(store: Store):
    idea = store.create_idea("Old title\nold note")
    assert idea is not None
    store.update_idea(idea.id, "New title", "new note")
    refreshed = store.get_idea(idea.id)
    assert refreshed is not None
    assert (refreshed.title, refreshed.note) == ("New title", "new note")

    store.delete_idea(idea.id)
    assert store.get_idea(idea.id) is None


def test_mark_idea_opened(store: Store):
    idea = store.create_idea("Open me")
    assert idea is not None and idea.never_opened
    store.mark_idea_opened(idea.id)
    refreshed = store.get_idea(idea.id)
    assert refreshed is not None
    assert refreshed.last_opened_at is not None
    assert not refreshed.never_opened


def test_ideas_are_listed_newest_first(store: Store):
    for n in range(5):
        store.create_idea(f"Idea {n}")
    titles = [i.title for i in store.list_ideas()]
    assert titles == ["Idea 4", "Idea 3", "Idea 2", "Idea 1", "Idea 0"]


def test_search_matches_title_and_note(store: Store):
    store.create_idea("Clipboard tool\nexpires after a day")
    store.create_idea("RSS digest\nposts to telegram")
    store.create_idea("Thumbnail logger\ntracks CTR")

    assert [i.title for i in store.list_ideas(search="clipboard")] == ["Clipboard tool"]
    assert [i.title for i in store.list_ideas(search="telegram")] == ["RSS digest"]
    assert len(store.list_ideas(search="zzz")) == 0
    assert len(store.list_ideas(search="  ")) == 3


# ---------- recent and unearth ----------


def test_recent_returns_three_newest(store: Store):
    for n in range(6):
        store.create_idea(f"Idea {n}")
    assert [i.title for i in store.recent_ideas()] == ["Idea 5", "Idea 4", "Idea 3"]


def test_unearth_pool_excludes_recent_and_promoted(store: Store):
    made = [store.create_idea(f"Idea {n}") for n in range(6)]
    pool_titles = {i.title for i in store.unearth_candidates()}
    assert pool_titles == {"Idea 0", "Idea 1", "Idea 2"}

    promoted = made[0]
    assert promoted is not None
    store.promote_idea(promoted.id, "Idea 0 the app")
    assert {i.title for i in store.unearth_candidates()} == {"Idea 1", "Idea 2"}


def test_unearth_returns_nothing_below_four_ideas(store: Store):
    for n in range(3):
        store.create_idea(f"Idea {n}")
    assert store.unearth_candidates() == []
    assert store.unearth() is None


def test_unearth_never_returns_the_excluded_idea(store: Store):
    for n in range(8):
        store.create_idea(f"Idea {n}")
    shown = store.unearth()
    assert shown is not None
    for _ in range(40):
        again = store.unearth(exclude_id=shown.id)
        assert again is not None
        assert again.id != shown.id


def test_unearth_pool_of_one_excluded_yields_nothing(store: Store):
    for n in range(4):
        store.create_idea(f"Idea {n}")
    pool = store.unearth_candidates()
    assert len(pool) == 1
    assert store.unearth(exclude_id=pool[0].id) is None


def test_unearth_draws_from_the_whole_pool(store: Store):
    for n in range(9):
        store.create_idea(f"Idea {n}")
    expected = {i.id for i in store.unearth_candidates()}
    assert len(expected) == 6
    seen = {store.unearth().id for _ in range(400)}  # type: ignore[union-attr]
    assert seen == expected, "random draw should reach every buried idea"


# ---------- apps and promote ----------


def test_create_app_requires_a_name(store: Store):
    with pytest.raises(StoreError):
        store.create_app("   ")


def test_app_crud(store: Store):
    app = store.create_app(
        "Local AI Hub",
        description="Control panel for local AI services",
        github_url="https://github.com/kamsiob/local-ai-hub",
        version_label="v1.2.0",
        shipped=True,
    )
    assert app.shipped is True
    assert app.origin_idea_id is None
    assert not app.was_dug_from_an_idea

    store.update_app(app.id, name="Local AI Hub 2", shipped=False, notes="line\nline")
    refreshed = store.get_app(app.id)
    assert refreshed is not None
    assert refreshed.name == "Local AI Hub 2"
    assert refreshed.shipped is False
    assert refreshed.notes == "line\nline"

    store.delete_app(app.id)
    assert store.get_app(app.id) is None


def test_update_app_rejects_unknown_fields(store: Store):
    app = store.create_app("Dig")
    with pytest.raises(StoreError):
        store.update_app(app.id, priority="high")


def test_apps_are_listed_alphabetically(store: Store):
    for name in ["logbook", "Bearings", "dig", "Local AI Hub"]:
        store.create_app(name)
    assert [a.name for a in store.list_apps()] == [
        "Bearings",
        "dig",
        "Local AI Hub",
        "logbook",
    ]


def test_promote_links_idea_to_app(store: Store):
    idea = store.create_idea("Pocket wiki for the channel\none markdown file per video")
    assert idea is not None
    app = store.promote_idea(
        idea.id,
        name=idea.title,
        description=idea.note,
        github_url="https://github.com/kamsiob/pocket-wiki",
    )

    assert app.origin_idea_id == idea.id
    assert app.was_dug_from_an_idea
    assert app.name == "Pocket wiki for the channel"

    promoted = store.get_idea(idea.id)
    assert promoted is not None
    assert promoted.promoted_app_id == app.id
    assert promoted.is_promoted


def test_promoted_idea_leaves_the_pool_but_survives(store: Store):
    idea = store.create_idea("Becomes an app")
    assert idea is not None
    store.promote_idea(idea.id, "Becomes an app")

    assert store.list_ideas() == []
    shown = store.list_ideas(include_promoted=True)
    assert len(shown) == 1
    assert shown[0].id == idea.id


def test_cannot_promote_twice(store: Store):
    idea = store.create_idea("Only once")
    assert idea is not None
    store.promote_idea(idea.id, "Only once")
    with pytest.raises(StoreError):
        store.promote_idea(idea.id, "Again")


def test_promote_missing_idea_fails(store: Store):
    with pytest.raises(StoreError):
        store.promote_idea(999, "Ghost")


# ---------- sheets ----------


def test_add_and_list_sheet_items(store: Store):
    app = store.create_app("Dig")
    store.add_sheet_item(app.id, FEATURE, "Disk usage per model")
    store.add_sheet_item(app.id, FEATURE, "One-click log bundle")
    store.add_sheet_item(app.id, BUG, "Status lamp goes stale")

    features = store.list_sheet_items(app.id, FEATURE)
    assert [f.text for f in features] == ["One-click log bundle", "Disk usage per model"]
    assert len(store.list_sheet_items(app.id, BUG)) == 1


def test_empty_sheet_item_adds_nothing(store: Store):
    app = store.create_app("Dig")
    assert store.add_sheet_item(app.id, FEATURE, "   ") is None
    assert store.list_sheet_items(app.id, FEATURE) == []


def test_bad_sheet_kind_is_refused(store: Store):
    app = store.create_app("Dig")
    with pytest.raises(StoreError):
        store.add_sheet_item(app.id, "chore", "not a thing")
    with pytest.raises(StoreError):
        store.list_sheet_items(app.id, "chore")


def test_toggle_sets_and_clears_done_at(store: Store):
    app = store.create_app("Dig")
    item = store.add_sheet_item(app.id, FEATURE, "Toggle me")
    assert item is not None and not item.done

    assert store.toggle_sheet_item(item.id) is True
    done = store.get_sheet_item(item.id)
    assert done is not None and done.done and done.done_at is not None

    assert store.toggle_sheet_item(item.id) is False
    undone = store.get_sheet_item(item.id)
    assert undone is not None and not undone.done and undone.done_at is None


def test_done_items_sink_below_open(store: Store):
    app = store.create_app("Dig")
    first = store.add_sheet_item(app.id, FEATURE, "First")
    store.add_sheet_item(app.id, FEATURE, "Second")
    store.add_sheet_item(app.id, FEATURE, "Third")
    assert first is not None

    store.toggle_sheet_item(first.id)  # oldest becomes done
    texts = [i.text for i in store.list_sheet_items(app.id, FEATURE)]
    assert texts == ["Third", "Second", "First"]
    assert store.list_sheet_items(app.id, FEATURE)[-1].done


def test_sheet_counts_are_live(store: Store):
    app = store.create_app("Dig")
    assert str(store.sheet_counts(app.id, FEATURE)) == "0 open · 0 done"

    a = store.add_sheet_item(app.id, FEATURE, "A")
    store.add_sheet_item(app.id, FEATURE, "B")
    store.add_sheet_item(app.id, BUG, "C")
    assert a is not None

    store.toggle_sheet_item(a.id)
    counts = store.sheet_counts(app.id, FEATURE)
    assert (counts.open, counts.done) == (1, 1)
    assert store.open_counts(app.id) == (1, 1)


def test_delete_sheet_item(store: Store):
    app = store.create_app("Dig")
    item = store.add_sheet_item(app.id, BUG, "Delete me")
    assert item is not None
    store.delete_sheet_item(item.id)
    assert store.get_sheet_item(item.id) is None


def test_deleting_an_app_removes_its_sheet_items(store: Store):
    app = store.create_app("Dig")
    store.add_sheet_item(app.id, FEATURE, "Goes away")
    store.delete_app(app.id)
    assert store.conn.execute("SELECT COUNT(*) FROM sheet_items").fetchone()[0] == 0


# ---------- attachments ----------


def test_attach_copies_and_leaves_the_original(store: Store, sample_file):
    app = store.create_app("Dig")
    src = sample_file("shot.png", b"\x89PNG fake")

    attachment = store.attach_file(app.id, src)

    assert src.exists(), "the original file must never be moved"
    assert src.read_bytes() == b"\x89PNG fake"
    stored = Path(attachment.stored_path)
    assert stored.is_file()
    assert stored.read_bytes() == src.read_bytes()
    assert stored.parent == store.app_attachments_dir(app.id)
    assert attachment.is_image is True
    assert attachment.size == len(b"\x89PNG fake")


def test_name_collisions_get_suffixes(store: Store, sample_file):
    app = store.create_app("Dig")
    first = store.attach_file(app.id, sample_file("notes.md", b"one"))

    other = sample_file("notes.md", b"one")  # same name, fresh content
    other.write_bytes(b"two")
    second = store.attach_file(app.id, other)
    other.write_bytes(b"three")
    third = store.attach_file(app.id, other)

    assert first.filename == "notes.md"
    assert second.filename == "notes-2.md"
    assert third.filename == "notes-3.md"
    assert Path(first.stored_path).read_bytes() == b"one"
    assert Path(second.stored_path).read_bytes() == b"two"
    assert Path(third.stored_path).read_bytes() == b"three"


def test_images_and_files_are_routed_apart(store: Store, sample_file):
    app = store.create_app("Dig")
    store.attach_file(app.id, sample_file("home.png"))
    store.attach_file(app.id, sample_file("diagram.SVG"))
    store.attach_file(app.id, sample_file("icons.zip"))
    store.attach_file(app.id, sample_file("release-notes.md"))

    images = [a.filename for a in store.list_attachments(app.id, images=True)]
    files = [a.filename for a in store.list_attachments(app.id, images=False)]
    assert images == ["home.png", "diagram.SVG"]
    assert files == ["icons.zip", "release-notes.md"]
    assert len(store.list_attachments(app.id)) == 4


def test_missing_source_file_is_refused(store: Store, tmp_path: Path):
    app = store.create_app("Dig")
    with pytest.raises(StoreError):
        store.attach_file(app.id, tmp_path / "not-here.png")


def test_deleting_an_attachment_removes_the_stored_copy(store: Store, sample_file):
    app = store.create_app("Dig")
    attachment = store.attach_file(app.id, sample_file("gone.png"))
    stored = Path(attachment.stored_path)
    assert stored.is_file()

    store.delete_attachment(attachment.id)
    assert not stored.exists()
    assert store.get_attachment(attachment.id) is None


def test_deleting_an_app_removes_its_attachment_folder(store: Store, sample_file):
    app = store.create_app("Dig")
    store.attach_file(app.id, sample_file("a.png"))
    store.attach_file(app.id, sample_file("b.zip"))
    folder = store.app_attachments_dir(app.id)
    assert folder.is_dir()

    store.delete_app(app.id)
    assert not folder.exists()
    assert store.conn.execute("SELECT COUNT(*) FROM attachments").fetchone()[0] == 0


# ---------- settings ----------


def test_settings_round_trip(store: Store):
    assert store.get_setting("appearance", "system") == "system"
    store.set_setting("appearance", "dark")
    assert store.get_setting("appearance") == "dark"
    store.set_setting("appearance", "light")
    assert store.get_setting("appearance") == "light"


# ---------- transactions ----------


def test_writes_run_in_a_real_transaction(store: Store):
    with store._write() as conn:
        assert conn.in_transaction, "a write must open a transaction, not autocommit"


def test_a_failed_write_rolls_back(store: Store):
    store.create_idea("Committed before the failure")
    with pytest.raises(ValueError):
        with store._write():
            store.conn.execute(
                "INSERT INTO ideas (title, note, created_at) VALUES (?, ?, ?)",
                ("Should vanish", "", "2026-01-01T00:00:00+00:00"),
            )
            raise ValueError("something went wrong mid-write")

    titles = [i.title for i in store.list_ideas()]
    assert titles == ["Committed before the failure"]


class _ConnectionThatFailsOn:
    """Passes everything through until it sees the statement it should choke on."""

    def __init__(self, real: sqlite3.Connection, doomed_fragment: str):
        self._real = real
        self._doomed = doomed_fragment

    def execute(self, sql: str, *args, **kwargs):
        if self._doomed in sql:
            raise sqlite3.OperationalError("disk gave out mid-promote")
        return self._real.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_promote_is_all_or_nothing(store: Store):
    idea = store.create_idea("Promote me")
    assert idea is not None

    real = store._conn
    store._conn = _ConnectionThatFailsOn(real, "promoted_app_id = ?")  # type: ignore[assignment]
    try:
        with pytest.raises(sqlite3.OperationalError):
            store.promote_idea(idea.id, "Promote me")
    finally:
        store._conn = real

    # No orphan app, and the idea is still unpromoted and available.
    assert store.list_apps() == []
    still_there = store.get_idea(idea.id)
    assert still_there is not None
    assert not still_there.is_promoted
    assert [i.title for i in store.list_ideas()] == ["Promote me"]


# ---------- corrupt database recovery ----------


def test_corrupt_database_is_set_aside_and_replaced(data_dir: Path):
    db = data_dir / "dig.db"
    attachments = data_dir / "attachments"

    healthy = Store(db_file=db, attachments_root=attachments).open()
    healthy.create_idea("Written before the corruption")
    healthy.close()

    db.write_bytes(b"this is not a database, it is garbage" * 40)

    recovered = Store(db_file=db, attachments_root=attachments).open()
    assert recovered.recovery_notice is not None
    assert "fresh one" in recovered.recovery_notice
    assert recovered.list_ideas() == []

    recovered.create_idea("Written after the recovery")
    assert len(recovered.list_ideas()) == 1
    recovered.close()

    set_aside = list(data_dir.glob("dig.db.broken-*"))
    assert len(set_aside) == 1, "the unreadable file must be kept, not deleted"
    assert set_aside[0].read_bytes().startswith(b"this is not a database")


def test_data_from_a_newer_dig_is_left_alone(data_dir: Path):
    db = data_dir / "dig.db"
    attachments = data_dir / "attachments"

    current = Store(db_file=db, attachments_root=attachments).open()
    current.create_idea("Written by a future Dig")
    current.set_setting("schema_version", str(SCHEMA_VERSION + 5))
    current.close()

    with pytest.raises(SchemaTooNewError):
        Store(db_file=db, attachments_root=attachments).open()

    # The good file is still the good file: nothing renamed, nothing replaced.
    assert list(data_dir.glob("dig.db.broken-*")) == []
    assert db.exists()


def test_healthy_database_reports_no_recovery_notice(store: Store):
    assert store.recovery_notice is None


def test_missing_database_starts_clean_without_a_notice(data_dir: Path):
    fresh = Store(
        db_file=data_dir / "nested" / "dig.db",
        attachments_root=data_dir / "nested" / "attachments",
    ).open()
    assert fresh.recovery_notice is None
    assert fresh.list_ideas() == []
    assert (data_dir / "nested" / "attachments").is_dir()
    fresh.close()


# ---------- persistence ----------


def test_everything_survives_a_restart(data_dir: Path, sample_file):
    db = data_dir / "dig.db"
    attachments = data_dir / "attachments"

    first = Store(db_file=db, attachments_root=attachments).open()
    idea = first.create_idea("Survives\nwith a note")
    assert idea is not None
    app = first.promote_idea(idea.id, "Survives", "with a note")
    first.add_sheet_item(app.id, FEATURE, "A feature")
    bug = first.add_sheet_item(app.id, BUG, "A bug")
    assert bug is not None
    first.toggle_sheet_item(bug.id)
    first.update_app(app.id, notes="para one\n\npara two")
    first.attach_file(app.id, sample_file("keep.png"))
    first.set_setting("appearance", "dark")
    first.close()

    second = Store(db_file=db, attachments_root=attachments).open()
    reopened = second.get_app(app.id)
    assert reopened is not None
    assert reopened.notes == "para one\n\npara two"
    assert reopened.origin_idea_id == idea.id
    assert second.sheet_counts(app.id, BUG).done == 1
    assert len(second.list_attachments(app.id, images=True)) == 1
    assert second.get_setting("appearance") == "dark"
    assert second.list_ideas() == []
    assert len(second.list_ideas(include_promoted=True)) == 1
    second.close()
