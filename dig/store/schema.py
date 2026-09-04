"""The database Dig keeps everything in.

One table per collection, every row carrying what a sync needs to reason about
it: when it was made, when it last changed, which device changed it, which
revision it is on, and whether it has been deleted. Deletes are tombstones, so
a device that has been offline for a week learns that something went away
instead of quietly bringing it back.

Every write goes through `dig.store.store.Store.write`, which updates the row
and appends to the oplog in the same transaction. Nothing writes here directly.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 3

# Sync columns every record table carries, in the same order everywhere.
SYNC_COLUMNS = """
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    rev        INTEGER NOT NULL DEFAULT 1,
    deleted    INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT
"""


def _record_table(name: str, columns: str) -> str:
    return f"CREATE TABLE IF NOT EXISTS {name} (\n  id TEXT PRIMARY KEY,\n{columns},\n{SYNC_COLUMNS}\n)"


# Every collection that holds records. The order matters only for readability.
TABLES = {
    "groups": "  name TEXT NOT NULL DEFAULT '',\n  color TEXT NOT NULL DEFAULT '',\n"
              "  priv INTEGER NOT NULL DEFAULT 0,\n  description TEXT NOT NULL DEFAULT '',\n"
              "  position INTEGER NOT NULL DEFAULT 0",
    "types": "  name TEXT NOT NULL DEFAULT '',\n  stages TEXT NOT NULL DEFAULT '[]',\n"
             "  checks TEXT NOT NULL DEFAULT '{}',\n  position INTEGER NOT NULL DEFAULT 0",
    "projects": "  name TEXT NOT NULL DEFAULT '',\n  group_id TEXT,\n  type_id TEXT,\n"
                "  stage INTEGER NOT NULL DEFAULT 0,\n  entered_at TEXT,\n"
                "  horizon TEXT NOT NULL DEFAULT 'later',\n  next TEXT NOT NULL DEFAULT '',\n"
                "  notes TEXT NOT NULL DEFAULT '',\n  pub INTEGER NOT NULL DEFAULT 1,\n"
                "  wait_what TEXT,\n  wait_since TEXT,\n  last_act TEXT,\n"
                "  quiet INTEGER NOT NULL DEFAULT 0,\n  parked INTEGER NOT NULL DEFAULT 0,\n"
                "  origin TEXT,\n  template_of TEXT,\n  example INTEGER NOT NULL DEFAULT 0,\n"
                "  position INTEGER NOT NULL DEFAULT 0",
    "checklist_items": "  project_id TEXT NOT NULL,\n  text TEXT NOT NULL DEFAULT '',\n"
                       "  done INTEGER NOT NULL DEFAULT 0,\n  tag TEXT NOT NULL DEFAULT '',\n"
                       "  position INTEGER NOT NULL DEFAULT 0",
    "decisions": "  project_id TEXT,\n  group_id TEXT,\n  text TEXT NOT NULL DEFAULT '',\n"
                 "  at TEXT,\n  supersedes_id TEXT,\n  superseded INTEGER NOT NULL DEFAULT 0",
    "releases": "  project_id TEXT NOT NULL,\n  v TEXT NOT NULL DEFAULT '',\n"
                "  at TEXT,\n  note TEXT NOT NULL DEFAULT ''",
    "people": "  project_id TEXT NOT NULL,\n  name TEXT NOT NULL DEFAULT '',\n"
              "  role TEXT NOT NULL DEFAULT '',\n  position INTEGER NOT NULL DEFAULT 0",
    "links": "  project_id TEXT,\n  group_id TEXT,\n  url TEXT NOT NULL DEFAULT '',\n"
             "  position INTEGER NOT NULL DEFAULT 0",
    "stage_history": "  project_id TEXT NOT NULL,\n  stage TEXT NOT NULL DEFAULT '',\n"
                     "  from_at TEXT,\n  to_at TEXT,\n  position INTEGER NOT NULL DEFAULT 0",
    "wait_history": "  project_id TEXT NOT NULL,\n  what TEXT NOT NULL DEFAULT '',\n"
                    "  days INTEGER NOT NULL DEFAULT 0,\n  position INTEGER NOT NULL DEFAULT 0",
    "log_entries": "  project_id TEXT,\n  group_id TEXT,\n  text TEXT NOT NULL DEFAULT '',\n"
                   "  at TEXT,\n  stage TEXT NOT NULL DEFAULT '',\n"
                   "  highlight INTEGER NOT NULL DEFAULT 0",
    "ideas": "  text TEXT NOT NULL DEFAULT '',\n  descr TEXT NOT NULL DEFAULT '',\n"
             "  at TEXT,\n  opened TEXT,\n  group_id TEXT,\n"
             "  example INTEGER NOT NULL DEFAULT 0,\n  position INTEGER NOT NULL DEFAULT 0",
    "inbox": "  text TEXT NOT NULL DEFAULT '',\n  kind TEXT NOT NULL DEFAULT 'idea',\n"
             "  at TEXT,\n  guess TEXT,\n  example INTEGER NOT NULL DEFAULT 0,\n"
             "  position INTEGER NOT NULL DEFAULT 0",
    "library": "  kind TEXT NOT NULL DEFAULT 'link',\n  title TEXT NOT NULL DEFAULT '',\n"
               "  meta TEXT NOT NULL DEFAULT '',\n  group_id TEXT,\n  file_id TEXT,\n"
               "  example INTEGER NOT NULL DEFAULT 0,\n  position INTEGER NOT NULL DEFAULT 0",
    "activity": "  group_id TEXT,\n  project_id TEXT,\n  text TEXT NOT NULL DEFAULT '',\n"
                "  at TEXT,\n  kind TEXT NOT NULL DEFAULT 'move',\n"
                "  example INTEGER NOT NULL DEFAULT 0",
    "files": "  sha256 TEXT NOT NULL,\n  name TEXT NOT NULL DEFAULT '',\n"
             "  mime TEXT NOT NULL DEFAULT '',\n  ext TEXT NOT NULL DEFAULT '',\n"
             "  size INTEGER NOT NULL DEFAULT 0,\n  added_at TEXT,\n"
             "  project_id TEXT,\n  group_id TEXT,\n  doc_id TEXT NOT NULL DEFAULT '',\n"
             "  version TEXT NOT NULL DEFAULT '',\n  descr TEXT NOT NULL DEFAULT '',\n"
             "  stage TEXT NOT NULL DEFAULT '',\n  previous_file_id TEXT,\n"
             "  superseded INTEGER NOT NULL DEFAULT 0,\n  example INTEGER NOT NULL DEFAULT 0,\n"
             "  position INTEGER NOT NULL DEFAULT 0",
    "templates": "  name TEXT NOT NULL DEFAULT '',\n  type_id TEXT,\n"
                 "  payload TEXT NOT NULL DEFAULT '{}'",
}

# Tables that are this device's business only, and never sync as records.
_LOCAL = """
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  rev   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS oplog (
  seq        INTEGER PRIMARY KEY AUTOINCREMENT,
  collection TEXT NOT NULL,
  record_id  TEXT NOT NULL,
  rev        INTEGER NOT NULL,
  op         TEXT NOT NULL CHECK (op IN ('create','update','delete')),
  payload    TEXT NOT NULL,
  at         TEXT NOT NULL,
  device     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL DEFAULT '',
  is_self     INTEGER NOT NULL DEFAULT 0,
  token       TEXT,
  paired_at   TEXT,
  last_synced TEXT,
  last_cursor INTEGER NOT NULL DEFAULT 0,
  revoked     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS conflicts (
  id         TEXT PRIMARY KEY,
  collection TEXT NOT NULL,
  record_id  TEXT NOT NULL,
  at         TEXT NOT NULL,
  device     TEXT NOT NULL,
  reason     TEXT NOT NULL DEFAULT '',
  losing     TEXT NOT NULL,
  seen       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS blobs (
  sha256     TEXT PRIMARY KEY,
  size       INTEGER NOT NULL DEFAULT 0,
  mime       TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_oplog_seq        ON oplog(seq);
CREATE INDEX IF NOT EXISTS idx_oplog_record     ON oplog(collection, record_id);
CREATE INDEX IF NOT EXISTS idx_conflicts_seen   ON conflicts(seen);
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_items_project    ON checklist_items(project_id);
CREATE INDEX IF NOT EXISTS idx_decisions_owner  ON decisions(project_id, group_id);
CREATE INDEX IF NOT EXISTS idx_releases_project ON releases(project_id);
CREATE INDEX IF NOT EXISTS idx_people_project   ON people(project_id);
CREATE INDEX IF NOT EXISTS idx_links_owner      ON links(project_id, group_id);
CREATE INDEX IF NOT EXISTS idx_stagehist_proj   ON stage_history(project_id);
CREATE INDEX IF NOT EXISTS idx_waithist_proj    ON wait_history(project_id);
CREATE INDEX IF NOT EXISTS idx_logs_owner       ON log_entries(project_id, group_id);
CREATE INDEX IF NOT EXISTS idx_files_owner      ON files(project_id, group_id);
CREATE INDEX IF NOT EXISTS idx_files_sha        ON files(sha256);
CREATE INDEX IF NOT EXISTS idx_projects_group   ON projects(group_id);
"""


class SchemaTooNewError(RuntimeError):
    """Written by a newer Dig. The file is intact, so never set it aside."""


def statements(script: str) -> list[str]:
    return [s.strip() for s in script.split(";") if s.strip()]


def read_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    except sqlite3.OperationalError:
        return 0
    if row is None:
        return 0
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return 0


def create(conn: sqlite3.Connection) -> None:
    """Lay the whole schema down. Safe to run on a database that has it."""
    for name, columns in TABLES.items():
        conn.execute(_record_table(name, columns))
    for statement in statements(_LOCAL):
        conn.execute(statement)
    for statement in statements(_INDEXES):
        conn.execute(statement)
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )


def ensure(conn: sqlite3.Connection) -> int:
    """Bring a database up to date, refusing one written by a newer Dig."""
    version = read_version(conn)
    if version > SCHEMA_VERSION:
        raise SchemaTooNewError(
            f"This file was written by a newer Dig (format {version}, this one reads {SCHEMA_VERSION})."
        )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=OFF")
    with conn:
        create(conn)
    return SCHEMA_VERSION
