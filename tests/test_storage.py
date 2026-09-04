"""The state document store: round trips, atomicity, history, and recovery."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from dig.storage import SCHEMA_VERSION, StateStore, StateTooNewError

SAMPLE = {
    "org": "Example Studio",
    "you": "Alex",
    "theme": "light",
    "setupDone": True,
    "groups": [{"id": "kam", "name": "Kamsiob", "color": "#0BA39E", "priv": False}],
    "projects": [],
    "ideas": [],
    "inbox": [],
    "library": [],
    "activity": [],
    "ui": {"filterGroup": "all", "sort": "activity"},
}


def dump(state: dict) -> str:
    return json.dumps(state)


def test_load_on_a_fresh_machine_returns_nothing(store: StateStore) -> None:
    result = store.load()
    assert result.state is None
    assert result.notice == ""
    assert result.recovered is False


def test_save_then_load_round_trips(store: StateStore) -> None:
    store.save(dump(SAMPLE))
    result = store.load()
    assert result.state == SAMPLE
    assert result.recovered is False


def test_save_refuses_a_broken_document(store: StateStore) -> None:
    with pytest.raises(ValueError):
        store.save("{not json")
    assert not store.db_path.exists()


def test_save_writes_the_schema_version_and_a_timestamp(store: StateStore) -> None:
    store.save(dump(SAMPLE))
    conn = sqlite3.connect(str(store.db_path))
    try:
        row = conn.execute(
            "SELECT id, schema_version, updated_at FROM state"
        ).fetchall()
    finally:
        conn.close()
    assert len(row) == 1
    assert row[0][0] == 1
    assert row[0][1] == SCHEMA_VERSION
    assert row[0][2]


def test_save_leaves_no_temporary_files_behind(store: StateStore) -> None:
    for index in range(3):
        store.save(dump({**SAMPLE, "n": index}))
    leftovers = list(store.db_path.parent.glob("dig.db.tmp-*"))
    assert leftovers == []


def test_a_failed_save_leaves_the_old_file_untouched(store: StateStore) -> None:
    store.save(dump(SAMPLE))
    before = store.db_path.read_bytes()
    with pytest.raises(ValueError):
        store.save("}}}")
    assert store.db_path.read_bytes() == before
    assert store.load().state == SAMPLE


def test_history_keeps_a_snapshot_per_save(store: StateStore) -> None:
    for index in range(5):
        store.save(dump({**SAMPLE, "n": index}))
    files = store.history_files()
    assert len(files) == 5
    newest = json.loads(files[0].read_text(encoding="utf-8"))
    assert newest["n"] == 4


def test_history_rotates_at_twenty(data_dir: Path) -> None:
    store = StateStore(data_dir / "dig.db", data_dir / "history")
    for index in range(26):
        store.save(dump({**SAMPLE, "n": index}))
    files = store.history_files()
    assert len(files) == 20
    kept = {json.loads(p.read_text(encoding="utf-8"))["n"] for p in files}
    assert kept == set(range(6, 26))


def test_history_leaves_no_partial_files(store: StateStore) -> None:
    store.save(dump(SAMPLE))
    assert list(store.history_dir.glob(".state-*.tmp")) == []


def test_a_corrupt_file_recovers_from_the_newest_history(store: StateStore) -> None:
    store.save(dump({**SAMPLE, "n": 1}))
    store.save(dump({**SAMPLE, "n": 2}))
    store.db_path.write_bytes(b"this is not a database")

    result = store.load()
    assert result.recovered is True
    assert result.state["n"] == 2
    assert "could not be read" in result.notice
    assert "went back to the last good save" in result.notice
    assert list(store.db_path.parent.glob("dig.db.broken-*"))


def test_a_corrupt_file_with_no_history_starts_fresh(data_dir: Path) -> None:
    store = StateStore(data_dir / "dig.db", data_dir / "history")
    store.db_path.write_bytes(b"garbage")

    result = store.load()
    assert result.recovered is True
    assert result.state is None
    assert "started fresh" in result.notice
    assert list(store.db_path.parent.glob("dig.db.broken-*"))


def test_recovery_skips_an_unreadable_snapshot(store: StateStore) -> None:
    store.save(dump({**SAMPLE, "n": 1}))
    store.save(dump({**SAMPLE, "n": 2}))
    newest, older = store.history_files()[0], store.history_files()[1]
    newest.write_text("{ broken", encoding="utf-8")
    store.db_path.write_bytes(b"garbage")

    result = store.load()
    assert result.state == json.loads(older.read_text(encoding="utf-8"))


def test_the_broken_file_is_kept_not_deleted(store: StateStore) -> None:
    store.save(dump(SAMPLE))
    store.db_path.write_bytes(b"garbage")
    store.load()
    broken = list(store.db_path.parent.glob("dig.db.broken-*"))
    assert len(broken) == 1
    assert broken[0].read_bytes() == b"garbage"


def test_a_database_with_no_state_row_is_treated_as_corrupt(store: StateStore) -> None:
    store.save(dump(SAMPLE))
    conn = sqlite3.connect(str(store.db_path))
    try:
        conn.execute("DELETE FROM state")
        conn.commit()
    finally:
        conn.close()

    result = store.load()
    assert result.recovered is True
    assert result.state == SAMPLE  # came back from history


def test_a_newer_format_is_refused_and_never_set_aside(store: StateStore) -> None:
    store.save(dump(SAMPLE))
    conn = sqlite3.connect(str(store.db_path))
    try:
        conn.execute("UPDATE state SET schema_version = 99")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(StateTooNewError):
        store.load()
    assert store.db_path.exists()
    assert list(store.db_path.parent.glob("dig.db.broken-*")) == []


def test_unicode_survives_the_round_trip(store: StateStore) -> None:
    state = {**SAMPLE, "org": "Café Beñíta", "you": "Karím"}
    store.save(dump(state))
    assert store.load().state["org"] == "Café Beñíta"


def test_a_large_document_round_trips(store: StateStore) -> None:
    state = {**SAMPLE, "projects": [{"id": f"p{i}", "notes": "x" * 500} for i in range(400)]}
    store.save(dump(state))
    assert len(store.load().state["projects"]) == 400
