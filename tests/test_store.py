"""The record store: round trips, the oplog, tombstones, blobs, and recovery."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

import pytest

from dig.store import BlobStore, SchemaTooNewError, Store
from dig.store import records
from dig.store.schema import SCHEMA_VERSION

SAMPLE = {
    "org": "Example Studio",
    "you": "Alex",
    "theme": "light",
    "setupDone": True,
    "ui": {"filterGroup": "all", "sort": "activity", "resurfId": None, "window": None},
    "groups": [
        {"id": "work", "name": "Work", "color": "#2457F5", "priv": False},
        {"id": "home", "name": "Home", "color": "#6B8F71", "priv": True},
    ],
    "types": [
        {"id": "task", "name": "Task", "stages": ["Planned", "In progress", "Done"], "check": {}},
    ],
    "projects": [
        {
            "id": "p1", "name": "Website refresh", "group": "work", "type": "task",
            "stage": 1, "enteredAt": "2026-08-29T09:00:00", "when": "now",
            "next": "Agree the page list", "notes": "Lead with the speed.",
            "pub": True, "wait": None, "lastAct": "2026-09-01T09:00:00",
            "quiet": False, "parked": False, "origin": None,
            "items": [
                {"id": "i1", "text": "Intake complete", "done": True, "tag": ""},
                {"id": "i2", "text": "Old gallery 404s", "done": False, "tag": "bug"},
            ],
            "decisions": [
                {"no": 1, "text": "Keep the structure.", "at": "2026-08-30T10:00:00",
                 "supersedes": None, "superseded": False},
            ],
            "files": [], "links": ["example.com"], "releases": [],
            "people": [{"n": "Client", "r": "approver"}],
            "hist": [{"stage": "Planned", "from": "2026-08-01T09:00:00", "to": "2026-08-29T09:00:00"}],
            "waitHist": [],
        },
        {
            "id": "p2", "name": "Quarterly report", "group": "work", "type": "task",
            "stage": 0, "enteredAt": "2026-09-01T09:00:00", "when": "next",
            "next": "", "notes": "", "pub": True,
            "wait": {"what": "the signed agreement", "since": "2026-09-01T09:00:00"},
            "lastAct": "2026-09-02T09:00:00", "quiet": False, "parked": False, "origin": None,
            "items": [], "files": [], "links": [], "releases": [], "people": [],
            "hist": [], "waitHist": [],
            "decisions": [
                {"no": 2, "text": "Same format as last quarter.", "at": "2026-09-02T10:00:00",
                 "supersedes": None, "superseded": False},
            ],
        },
    ],
    "ideas": [{"id": "e1", "text": "File receipts", "desc": "One rule.",
               "at": "2026-08-01T09:00:00", "opened": None, "group": ""}],
    "inbox": [{"id": "u1", "text": "Send the page list", "type": "todo",
               "at": "2026-09-03T09:00:00", "guess": "p1"}],
    "library": [{"id": "l1", "kind": "link", "title": "Checklist",
                 "meta": "example.org", "group": "work"}],
    "activity": [{"group": "work", "pid": "p1", "text": "Website refresh moved to In progress",
                  "at": "2026-08-29T09:00:00", "kind": "move"}],
}


@pytest.fixture()
def blobs(data_dir: Path) -> BlobStore:
    return BlobStore(data_dir / "blobs")


def oplog(store: Store) -> list[dict]:
    return store.changes_since(0, 100000)


# ------------------------------------------------------------------ round trip


def test_a_fresh_machine_has_nothing(store: Store) -> None:
    assert store.load().state is None


def test_the_whole_document_survives_a_round_trip(store: Store) -> None:
    store.save_state(SAMPLE)
    back = store.load().state

    assert back["org"] == "Example Studio"
    assert back["theme"] == "light"
    assert [g["name"] for g in back["groups"]] == ["Work", "Home"]
    assert back["groups"][1]["priv"] is True
    assert [t["stages"] for t in back["types"]] == [["Planned", "In progress", "Done"]]

    first = back["projects"][0]
    assert first["name"] == "Website refresh"
    assert first["next"] == "Agree the page list"
    assert [i["text"] for i in first["items"]] == ["Intake complete", "Old gallery 404s"]
    assert first["items"][1]["tag"] == "bug"
    assert first["links"] == ["example.com"]
    assert first["people"] == [{"id": first["people"][0]["id"], "n": "Client", "r": "approver"}]
    assert first["hist"][0]["stage"] == "Planned"

    second = back["projects"][1]
    assert second["wait"] == {"what": "the signed agreement", "since": "2026-09-01T09:00:00"}

    assert [i["text"] for i in back["ideas"]] == ["File receipts"]
    assert back["inbox"][0]["guess"] == "p1"
    assert back["library"][0]["kind"] == "link"
    assert back["activity"][0]["kind"] == "move"


def test_saving_the_same_document_twice_writes_nothing(store: Store) -> None:
    store.save_state(SAMPLE)
    before = len(oplog(store))
    again = store.save_state(store.load().state)
    assert again == {"created": 0, "updated": 0, "deleted": 0}
    assert len(oplog(store)) == before


def test_one_edit_writes_exactly_one_change(store: Store) -> None:
    store.save_state(SAMPLE)
    before = len(oplog(store))
    state = store.load().state
    state["projects"][0]["next"] = "Something else"
    assert store.save_state(state) == {"created": 0, "updated": 1, "deleted": 0}
    assert len(oplog(store)) == before + 1
    assert store.load().state["projects"][0]["next"] == "Something else"


# ----------------------------------------------------------------- the oplog


def test_the_oplog_records_every_mutation_exactly_once(store: Store) -> None:
    store.save_state(SAMPLE)
    entries = oplog(store)
    creates = [e for e in entries if e["op"] == "create"]
    ids = [(e["collection"], e["record_id"]) for e in creates]
    assert len(ids) == len(set(ids)), "nothing was written twice"

    state = store.load().state
    state["projects"][0]["items"].append({"id": "i3", "text": "Ship it", "done": False, "tag": ""})
    state["projects"][0]["notes"] = "Changed"
    store.save_state(state)

    fresh = oplog(store)[len(entries):]
    kinds = sorted((e["collection"], e["op"]) for e in fresh)
    assert kinds == [("checklist_items", "create"), ("projects", "update")]


def test_every_op_carries_this_device_and_a_rising_revision(store: Store) -> None:
    store.save_state(SAMPLE)
    state = store.load().state
    for round_number in range(3):
        state["projects"][0]["notes"] = f"note {round_number}"
        store.save_state(state)
    project_ops = [e for e in oplog(store) if e["collection"] == "projects" and e["record_id"] == "p1"]
    assert [e["rev"] for e in project_ops] == [1, 2, 3, 4]
    assert {e["device"] for e in project_ops} == {store.device_id}


def test_the_cursor_moves_with_the_log(store: Store) -> None:
    store.save_state(SAMPLE)
    first = store.meta()["cursor"]
    assert first > 0
    assert store.changes_since(first) == []
    state = store.load().state
    state["org"] = "Another name"
    store.save_state(state)
    assert store.meta()["cursor"] > first
    assert len(store.changes_since(first)) == 1


# --------------------------------------------------------------- tombstones


def test_a_delete_leaves_a_tombstone_and_does_not_come_back(store: Store) -> None:
    store.save_state(SAMPLE)
    state = store.load().state
    state["ideas"] = []
    store.save_state(state)

    assert store.load().state["ideas"] == []
    conn = store.connect()
    row = conn.execute("SELECT deleted, deleted_at FROM ideas WHERE id='e1'").fetchone()
    assert row["deleted"] == 1 and row["deleted_at"]

    # A round trip must not resurrect it.
    store.save_state(store.load().state)
    assert store.load().state["ideas"] == []
    assert conn.execute("SELECT COUNT(*) c FROM ideas").fetchone()["c"] == 1


def test_a_tombstone_is_logged_as_a_delete(store: Store) -> None:
    store.save_state(SAMPLE)
    state = store.load().state
    state["projects"] = [state["projects"][1]]
    store.save_state(state)
    deletes = [e for e in oplog(store) if e["op"] == "delete"]
    assert ("projects", "p1") in [(e["collection"], e["record_id"]) for e in deletes]
    # its children go too
    assert ("checklist_items", "i1") in [(e["collection"], e["record_id"]) for e in deletes]


def test_recently_deleted_lists_them_and_restore_brings_one_back(store: Store) -> None:
    store.save_state(SAMPLE)
    state = store.load().state
    state["ideas"] = []
    store.save_state(state)

    recent = store.deleted_since(30)
    assert [(r["collection"], r["id"]) for r in recent if r["collection"] == "ideas"] == [("ideas", "e1")]

    assert store.restore("ideas", "e1") is True
    assert [i["id"] for i in store.load().state["ideas"]] == ["e1"]


def test_tombstones_are_only_purged_once_every_device_has_seen_them(store: Store) -> None:
    store.save_state(SAMPLE)
    state = store.load().state
    state["ideas"] = []
    store.save_state(state)
    assert store.purge_tombstones(acknowledged_by_all=False) == 0
    conn = store.connect()
    assert conn.execute("SELECT COUNT(*) c FROM ideas").fetchone()["c"] == 1


# ------------------------------------------------------------------- numbers


def test_decision_numbers_are_derived_dense_and_global(store: Store) -> None:
    store.save_state(SAMPLE)
    numbers = [d["no"] for p in store.load().state["projects"] for d in p["decisions"]]
    assert sorted(numbers) == [1, 2], "numbered across every project, not within one"

    conn = store.connect()
    assert "no" not in {c[1] for c in conn.execute("PRAGMA table_info(decisions)")}, (
        "the number is never stored"
    )


def test_decision_numbering_is_the_same_on_every_device(store: Store, data_dir: Path) -> None:
    store.save_state(SAMPLE)
    mine = {d["text"]: d["no"] for p in store.load().state["projects"] for d in p["decisions"]}

    other = Store(data_dir / "other.db", data_dir / "history2")
    other.save_state(SAMPLE)
    theirs = {d["text"]: d["no"] for p in other.load().state["projects"] for d in p["decisions"]}
    assert mine == theirs, "two devices reach the same numbering from the same records"


def test_numbering_stays_dense_when_one_is_deleted(store: Store) -> None:
    store.save_state(SAMPLE)
    state = store.load().state
    state["projects"][0]["decisions"] = []
    store.save_state(state)
    numbers = [d["no"] for p in store.load().state["projects"] for d in p["decisions"]]
    assert numbers == [1], "the survivor renumbers rather than leaving a hole"


def test_a_superseding_decision_keeps_pointing_at_the_right_one(store: Store) -> None:
    state = json.loads(json.dumps(SAMPLE))
    state["projects"][0]["decisions"].append(
        {"no": 3, "text": "Rewrite it after all.", "at": "2026-09-03T10:00:00",
         "supersedes": 1, "superseded": False}
    )
    state["projects"][0]["decisions"][0]["superseded"] = True
    store.save_state(state)

    decisions = store.load().state["projects"][0]["decisions"]
    original = next(d for d in decisions if d["text"] == "Keep the structure.")
    replacement = next(d for d in decisions if d["text"] == "Rewrite it after all.")
    assert replacement["supersedes"] == original["no"]
    assert original["superseded"] is True


# ---------------------------------------------------------------------- ids


def test_ids_are_unique_when_several_threads_make_them_at_once() -> None:
    made: list[str] = []
    lock = threading.Lock()

    def work() -> None:
        mine = [records.derived_id("thing", i, threading.get_ident()) for i in range(200)]
        with lock:
            made.extend(mine)

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(made) == 1600
    assert len(set(made)) == 1600


def test_a_derived_id_is_the_same_everywhere_forever() -> None:
    assert records.derived_id("link", "project", "p1", "example.com") == records.derived_id(
        "link", "project", "p1", "example.com"
    )
    assert records.derived_id("link", "project", "p1", "example.com") != records.derived_id(
        "link", "project", "p2", "example.com"
    )


# -------------------------------------------------------------------- blobs


def test_identical_bytes_are_only_stored_once(blobs: BlobStore, tmp_path: Path) -> None:
    one = tmp_path / "one.txt"
    two = tmp_path / "two.txt"
    one.write_bytes(b"the same bytes")
    two.write_bytes(b"the same bytes")

    first = blobs.put(one)
    second = blobs.put(two)
    assert first.sha256 == second.sha256
    assert first.deduplicated is False and second.deduplicated is True
    assert len(blobs.every()) == 1


def test_a_blob_comes_back_byte_identical(blobs: BlobStore, tmp_path: Path) -> None:
    source = tmp_path / "spec.pdf"
    payload = bytes(range(256)) * 40
    source.write_bytes(payload)
    stored = blobs.put(source)

    out = blobs.copy_out(stored.sha256, tmp_path / "out" / "copy.pdf")
    assert out.read_bytes() == payload
    assert source.read_bytes() == payload, "the original is never touched"
    assert stored.mime == "application/pdf" and stored.ext == "PDF"


def test_cleanup_only_removes_what_nothing_points_at(blobs: BlobStore, tmp_path: Path) -> None:
    kept = tmp_path / "kept.txt"; kept.write_bytes(b"kept")
    loose = tmp_path / "loose.txt"; loose.write_bytes(b"loose")
    a = blobs.put(kept)
    b = blobs.put(loose)

    unreferenced = blobs.unreferenced({a.sha256})
    assert unreferenced == [b.sha256]
    blobs.remove(b.sha256)
    assert blobs.has(a.sha256) is True
    assert blobs.has(b.sha256) is False


def test_pasted_bytes_get_a_name_and_a_type(blobs: BlobStore) -> None:
    stored = blobs.put_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50, "Pasted 2026-09-04.png")
    assert stored.ext == "PNG" and stored.mime == "image/png"
    assert blobs.has(stored.sha256)


# ------------------------------------------------------------------ recovery


def test_a_newer_format_is_refused_and_the_file_is_left_alone(store: Store) -> None:
    store.save_state(SAMPLE)
    store.close()
    conn = sqlite3.connect(str(store.db_path))
    try:
        conn.execute("UPDATE meta SET value='99' WHERE key='schema_version'")
        conn.commit()
    finally:
        conn.close()

    fresh = Store(store.db_path, store.history_dir)
    with pytest.raises(SchemaTooNewError):
        fresh.load()
    assert store.db_path.exists()
    assert list(store.db_path.parent.glob("dig.db.broken-*")) == []


def test_a_read_only_store_refuses_to_write(store: Store) -> None:
    store.save_state(SAMPLE)
    store.read_only = True
    with pytest.raises(RuntimeError):
        store.save_state(SAMPLE)


def test_a_corrupt_file_recovers_from_the_newest_snapshot(store: Store) -> None:
    store.save_state(SAMPLE)
    edited = store.load().state
    edited["org"] = "Later name"
    store.save_state(edited)
    store.close()
    store.db_path.write_bytes(b"this is not a database")

    result = store.load()
    assert result.recovered is True
    assert result.state["org"] == "Later name"
    assert "could not be read" in result.notice
    assert list(store.db_path.parent.glob("dig.db.broken-*"))


def test_history_rotates_at_twenty(store: Store) -> None:
    for index in range(24):
        state = json.loads(json.dumps(SAMPLE))
        state["org"] = f"Name {index}"
        store.save_state(state)
    files = store.history_files()
    assert len(files) == 20
    newest = json.loads(files[0].read_text(encoding="utf-8"))
    assert newest["org"] == "Name 23"


def test_history_leaves_no_partial_files(store: Store) -> None:
    store.save_state(SAMPLE)
    assert list(store.history_dir.glob(".state-*.tmp")) == []


# ------------------------------------------------------------------ geometry


def test_the_window_place_can_be_saved_on_its_own(store: Store) -> None:
    store.save_state(SAMPLE)
    before = len(oplog(store))
    store.update_window({"x": 10, "y": 20, "w": 1200, "h": 800, "max": False})
    assert store.load().state["ui"]["window"]["w"] == 1200
    assert len(oplog(store)) == before + 1
    # writing the same geometry again changes nothing
    store.update_window({"x": 10, "y": 20, "w": 1200, "h": 800, "max": False})
    assert len(oplog(store)) == before + 1


# -------------------------------------------------------------------- schema


def test_the_schema_version_is_stamped_in_the_file(store: Store) -> None:
    store.save_state(SAMPLE)
    conn = store.connect()
    row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    assert int(row["value"]) == SCHEMA_VERSION
    assert store.meta()["schema_version"] == SCHEMA_VERSION


def test_this_device_has_an_identity(store: Store) -> None:
    assert len(store.device_id) == 36
    assert store.device_name()
    conn = store.connect()
    assert conn.execute("SELECT COUNT(*) c FROM devices WHERE is_self=1").fetchone()["c"] == 1


def test_every_collection_has_the_sync_columns(store: Store) -> None:
    conn = store.connect()
    for name in records.COLLECTIONS:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({name})")}
        assert {"id", "created_at", "updated_at", "updated_by", "rev", "deleted", "deleted_at"} <= columns, name


def test_restoring_a_project_brings_its_children_back(store: Store) -> None:
    store.save_state(SAMPLE)
    state = store.load().state
    state["projects"] = [p for p in state["projects"] if p["id"] != "p1"]
    store.save_state(state)

    assert store.load().state["projects"][0]["id"] == "p2"
    conn = store.connect()
    assert conn.execute("SELECT deleted FROM checklist_items WHERE id='i1'").fetchone()["deleted"] == 1

    assert store.restore("projects", "p1") is True
    back = next(p for p in store.load().state["projects"] if p["id"] == "p1")
    assert [i["text"] for i in back["items"]] == ["Intake complete", "Old gallery 404s"]
    assert [d["text"] for d in back["decisions"]] == ["Keep the structure."]
    assert back["people"][0]["n"] == "Client"
    assert back["links"] == ["example.com"]
    assert back["hist"][0]["stage"] == "Planned"
