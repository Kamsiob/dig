"""Bringing Dig v1's data into v2, exactly as docs/V2_MIGRATION.md describes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from dig import migrate_v1, paths
from dig.store import Store

V1_SCHEMA = """
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
    last_opened_at TEXT, promoted_app_id INTEGER);
CREATE TABLE apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
    github_url TEXT NOT NULL DEFAULT '', version_label TEXT NOT NULL DEFAULT '',
    shipped INTEGER NOT NULL DEFAULT 0, origin_idea_id INTEGER,
    created_at TEXT NOT NULL);
CREATE TABLE sheet_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT, app_id INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('feature','bug')), text TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, done_at TEXT);
CREATE TABLE attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, app_id INTEGER NOT NULL,
    filename TEXT NOT NULL, stored_path TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0, is_image INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL);
"""


@pytest.fixture()
def v1_home(tmp_path: Path, monkeypatch) -> Path:
    """A data folder holding a fully populated Dig v1."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    root = paths.ensure_data_dirs()

    conn = sqlite3.connect(str(paths.db_path()))
    try:
        conn.executescript(V1_SCHEMA)
        conn.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            [("schema_version", "1"), ("appearance", "dark"), ("window_geometry", "x")],
        )
        conn.executemany(
            "INSERT INTO ideas (id,title,note,created_at,last_opened_at,promoted_app_id)"
            " VALUES (?,?,?,?,?,?)",
            [
                (1, "Receipt filing", "One folder, one rule.", "2026-05-01T10:00:00", None, None),
                (2, "Walking route map", "Somewhere new each week.", "2026-04-02T10:00:00", "2026-06-01T10:00:00", None),
                (3, "Recipe Box", "Only the ones cooked twice.", "2026-01-05T10:00:00", None, 2),
            ],
        )
        conn.executemany(
            "INSERT INTO apps (id,name,description,notes,github_url,version_label,"
            "shipped,origin_idea_id,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (1, "Field Notes", "One small tool", "Ship it, then leave it alone.",
                 "example.com/field-notes", "", 0, None, "2026-06-10T09:00:00"),
                (2, "Recipe Box", "A box for recipes worth keeping", "",
                 "", "1.0.0", 1, 3, "2026-02-01T09:00:00"),
            ],
        )
        conn.executemany(
            "INSERT INTO sheet_items (id,app_id,kind,text,done,created_at,done_at)"
            " VALUES (?,?,?,?,?,?,?)",
            [
                (1, 1, "feature", "Export PDF", 0, "2026-06-11T09:00:00", None),
                (2, 1, "bug", "Search misses accents", 1, "2026-06-12T09:00:00", "2026-06-13T09:00:00"),
                (3, 2, "bug", "Import drops the last row", 0, "2026-02-02T09:00:00", None),
            ],
        )
        store = paths.attachments_dir() / "1"
        store.mkdir(parents=True, exist_ok=True)
        (store / "spec.pdf").write_bytes(b"x" * 2048)
        conn.execute(
            "INSERT INTO attachments (id,app_id,filename,stored_path,size,is_image,added_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (1, 1, "spec.pdf", str(store / "spec.pdf"), 2048, 0, "2026-06-14T09:00:00"),
        )
        conn.commit()
    finally:
        conn.close()
    return root


def run_migration() -> tuple[str, dict]:
    store = Store(paths.db_path(), paths.history_dir())
    notice = migrate_v1.migrate_if_needed(store)
    return notice, store.load().state


def test_a_v1_file_is_recognized(v1_home: Path) -> None:
    assert migrate_v1.looks_like_v1(paths.db_path()) is True


def test_a_v2_file_is_not_mistaken_for_v1(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    paths.ensure_data_dirs()
    Store(paths.db_path(), paths.history_dir()).save_state({"projects": [], "org": "x"})
    assert migrate_v1.looks_like_v1(paths.db_path()) is False


def test_nothing_to_migrate_on_a_new_machine(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    paths.ensure_data_dirs()
    store = Store(paths.db_path(), paths.history_dir())
    assert migrate_v1.migrate_if_needed(store) == ""


def test_the_v1_file_is_kept(v1_home: Path) -> None:
    run_migration()
    backup = paths.v1_backup_path()
    assert backup.exists()
    conn = sqlite3.connect(str(backup))
    try:
        assert conn.execute("SELECT COUNT(*) FROM apps").fetchone()[0] == 2
    finally:
        conn.close()


def test_it_only_runs_once(v1_home: Path) -> None:
    run_migration()
    store = Store(paths.db_path(), paths.history_dir())
    assert migrate_v1.migrate_if_needed(store) == ""


def test_settings_carry_over(v1_home: Path) -> None:
    _, state = run_migration()
    assert state["theme"] == "dark"
    assert state["setupDone"] is True
    assert state["org"]


def test_one_apps_group_and_the_app_type(v1_home: Path) -> None:
    _, state = run_migration()
    assert [g["id"] for g in state["groups"]] == ["apps"]
    group = state["groups"][0]
    assert group["id"] == "apps" and group["name"] == "Apps"
    assert group["color"] == "#0BA39E" and group["priv"] is False
    assert [t["id"] for t in state["types"]] == ["app"]
    assert state["types"][0]["stages"] == [
        "Idea", "Plan", "Design", "Build", "Test", "Release", "Keep up"
    ]
    assert state["types"][0]["check"]["Keep up"] == ["Review the bug list"]


def test_apps_become_projects_at_the_right_stage(v1_home: Path) -> None:
    _, state = run_migration()
    by_name = {p["name"]: p for p in state["projects"]}

    building = by_name["Field Notes"]
    assert building["stage"] == 3  # Build
    assert building["when"] == "next"
    assert building["quiet"] is False
    assert building["notes"] == "Ship it, then leave it alone."
    assert building["links"] == ["example.com/field-notes"]
    assert building["group"] == "apps" and building["type"] == "app"
    assert building["pub"] is True

    shipped = by_name["Recipe Box"]
    assert shipped["stage"] == 6  # Keep up, the last stage
    assert shipped["when"] == "done"
    assert shipped["quiet"] is True


def test_a_description_stands_in_for_missing_notes(v1_home: Path) -> None:
    _, state = run_migration()
    shipped = next(p for p in state["projects"] if p["name"] == "Recipe Box")
    assert shipped["notes"] == "A box for recipes worth keeping"


def test_a_version_label_becomes_a_release(v1_home: Path) -> None:
    _, state = run_migration()
    shipped = next(p for p in state["projects"] if p["name"] == "Recipe Box")
    assert len(shipped["releases"]) == 1
    release = shipped["releases"][0]
    assert release["v"] == "1.0.0"
    assert release["at"] == "2026-02-01T09:00:00"
    assert release["note"] == "Carried over from Dig v1"
    building = next(p for p in state["projects"] if p["name"] == "Field Notes")
    assert building["releases"] == []


def test_sheet_lines_become_checklist_items_with_the_bug_tag(v1_home: Path) -> None:
    _, state = run_migration()
    building = next(p for p in state["projects"] if p["name"] == "Field Notes")
    assert building["items"] == [
        {"id": "v1s1", "text": "Export PDF", "done": False, "tag": ""},
        {"id": "v1s2", "text": "Search misses accents", "done": True, "tag": "bug"},
    ]


def test_attachments_are_taken_into_the_blob_store(v1_home: Path) -> None:
    from dig.store.blobs import BlobStore

    _, state = run_migration()
    building = next(p for p in state["projects"] if p["name"] == "Field Notes")
    assert len(building["files"]) == 1
    record = building["files"][0]

    assert record["type"] == "PDF"
    assert record["size"] == 2048
    assert len(record["sha256"]) == 64

    blobs = BlobStore(paths.blobs_dir())
    assert blobs.has(record["sha256"]), "the bytes came across"
    assert blobs.read(record["sha256"]) == b"x" * 2048
    assert (paths.attachments_dir() / "1" / "spec.pdf").exists(), "and v1's copy is left alone"


def test_ideas_come_across_except_the_promoted_one(v1_home: Path) -> None:
    _, state = run_migration()
    titles = [i["text"] for i in state["ideas"]]
    assert titles == ["Receipt filing", "Walking route map"]
    assert state["ideas"][0]["opened"] is None
    assert state["ideas"][1]["opened"] == "2026-06-01T10:00:00"
    assert state["ideas"][1]["desc"] == "Somewhere new each week."


def test_a_promoted_idea_becomes_the_projects_origin(v1_home: Path) -> None:
    _, state = run_migration()
    shipped = next(p for p in state["projects"] if p["name"] == "Recipe Box")
    assert shipped["origin"] == "Recipe Box"
    building = next(p for p in state["projects"] if p["name"] == "Field Notes")
    assert building["origin"] is None


def test_nothing_is_invented(v1_home: Path) -> None:
    _, state = run_migration()
    assert state["inbox"] == []
    assert state["library"] == []
    assert state["activity"] == []
    for project in state["projects"]:
        assert project["decisions"] == []
        assert project["people"] == []
        assert project["hist"] == []
        assert project["waitHist"] == []
        assert project["wait"] is None
        assert project["next"] == ""


def test_the_notice_says_what_came_across(v1_home: Path) -> None:
    notice, _ = run_migration()
    assert "2 apps" in notice
    assert "2 ideas" in notice
    assert "dig-v1.db.bak" in notice
    assert "—" not in notice


def test_the_document_matches_the_v2_shape(v1_home: Path) -> None:
    _, state = run_migration()
    assert {
        "org", "you", "theme", "setupDone", "groups", "types", "projects",
        "ideas", "inbox", "library", "activity", "ui",
    } <= set(state)
    assert set(state["ui"]) == {
        "filterGroup", "sort", "ideaSort", "libFilter", "publicOnly", "ptab",
        "resurfId", "window",
    }


def test_an_empty_v1_still_migrates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    paths.ensure_data_dirs()
    conn = sqlite3.connect(str(paths.db_path()))
    try:
        conn.executescript(V1_SCHEMA)
        conn.execute("INSERT INTO settings VALUES ('schema_version','1')")
        conn.commit()
    finally:
        conn.close()

    notice, state = run_migration()
    assert state["projects"] == [] and state["ideas"] == []
    assert "0 apps and 0 ideas" in notice
    assert state["setupDone"] is True
    assert len(state["groups"]) == 1 and len(state["types"]) == 1


def test_the_migrated_app_opens_on_home_and_shows_the_projects(v1_home, launch) -> None:
    ui = launch()
    assert ui.js("S.view") == "home", "someone with data is not asked to set up"
    assert ui.js("S.setupDone") is True
    assert sorted(p["name"] for p in ui.js("S.projects")) == ["Field Notes", "Recipe Box"]
    assert ui.js("S.theme") == "dark", "v1's appearance carried over"

    ui.run("S.view='projects';render();")
    body = ui.html()
    assert "Field Notes" in body and "Recipe Box" in body
    assert "Apps" in body


def test_the_migration_notice_is_shown_once(v1_home, launch) -> None:
    ui = launch()
    assert any("over from Dig v1" in t for t in ui.toasts())
    ui.restart()
    assert not any("over from Dig v1" in t for t in ui.toasts())


def test_a_migrated_project_reads_correctly_on_its_page(v1_home, launch) -> None:
    ui = launch()
    ui.run("S.view='project';S.projectId='v1a1';S.ptab='work';render();")
    body = ui.html()
    assert "Field Notes" in body
    assert "Build" in body
    assert "Export PDF" in body
    assert "Search misses accents" in body
    assert "spec.pdf" in body
    assert "example.com/field-notes" in body


def test_a_migrated_shipped_project_reads_as_finished(v1_home, launch) -> None:
    ui = launch()
    ui.run("S.view='project';S.projectId='v1a2';S.ptab='work';render();")
    assert "Keep up" in ui.html()
    assert ui.js("isLast(Pr('v1a2'))") is True
    assert "Recipe Box" in ui.text(".ph h1")
    assert "Finished" in ui.html(), "the horizon badge has a word for done"
    assert ui.count(".ph .r button[disabled]") == 1, "there is nowhere left to move it"


def test_the_origin_callout_shows_on_a_promoted_app(v1_home, launch) -> None:
    ui = launch()
    ui.run("S.view='project';S.projectId='v1a2';S.ptab='work';render();")
    assert "Started as an idea" in ui.html()


def test_a_migrated_week_report_invents_nothing(v1_home, launch) -> None:
    ui = launch()
    ui.run("S.view='week';render();")
    body = ui.html()
    assert "Nothing shipped in this period." in body
    assert "No stage changes in this period." in body
    assert "No decisions recorded in this period." in body
