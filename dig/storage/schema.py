"""Database schema and forward-only migrations.

The schema version lives in the settings table. Migrations only ever move
forward: each step takes the database from version N to version N+1 and is
never rewritten once it has shipped.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1
SCHEMA_VERSION_KEY = "schema_version"


class SchemaTooNewError(RuntimeError):
    """The file was written by a newer Dig. It is intact, so never set it aside."""

# Statements are kept separate rather than run through executescript(), which
# implicitly commits and would break the transaction wrapping the migration.
_INITIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ideas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL DEFAULT '',
    note            TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    last_opened_at  TEXT,
    promoted_app_id INTEGER REFERENCES apps(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS apps (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    notes          TEXT NOT NULL DEFAULT '',
    github_url     TEXT NOT NULL DEFAULT '',
    version_label  TEXT NOT NULL DEFAULT '',
    shipped        INTEGER NOT NULL DEFAULT 0,
    origin_idea_id INTEGER REFERENCES ideas(id) ON DELETE SET NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sheet_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id     INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL CHECK (kind IN ('feature', 'bug')),
    text       TEXT NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    done_at    TEXT
);

CREATE TABLE IF NOT EXISTS attachments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id      INTEGER NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    size        INTEGER NOT NULL DEFAULT 0,
    is_image    INTEGER NOT NULL DEFAULT 0,
    added_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ideas_created      ON ideas(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ideas_promoted     ON ideas(promoted_app_id);
CREATE INDEX IF NOT EXISTS idx_sheet_items_app    ON sheet_items(app_id, kind);
CREATE INDEX IF NOT EXISTS idx_attachments_app    ON attachments(app_id);
"""


def read_schema_version(conn: sqlite3.Connection) -> int:
    """The stored schema version, or 0 when the database is brand new."""
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (SCHEMA_VERSION_KEY,)
        ).fetchone()
    except sqlite3.OperationalError:
        return 0  # settings table does not exist yet
    if row is None:
        return 0
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return 0


def _write_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (SCHEMA_VERSION_KEY, str(version)),
    )


def _statements(script: str) -> list[str]:
    """Split a DDL script into individual statements."""
    return [s.strip() for s in script.split(";") if s.strip()]


def _migrate_0_to_1(conn: sqlite3.Connection) -> None:
    """Create the initial schema."""
    for statement in _statements(_INITIAL_SCHEMA):
        conn.execute(statement)


# Each entry takes the database from version N to N+1. Append, never edit.
_MIGRATIONS = {
    0: _migrate_0_to_1,
}


def migrate(conn: sqlite3.Connection) -> int:
    """Bring the database up to SCHEMA_VERSION. Returns the version applied.

    Runs in a single transaction so a failed migration leaves the database
    exactly as it was.
    """
    current = read_schema_version(conn)
    if current > SCHEMA_VERSION:
        # A newer Dig wrote this file. It is readable and whole, so it is left
        # exactly as it is: setting it aside would hide working data.
        raise SchemaTooNewError(
            f"This data was written by a newer version of Dig "
            f"(schema {current}, this build understands {SCHEMA_VERSION}). "
            f"Update Dig to open it."
        )

    # The connection is in autocommit mode, so the transaction is explicit:
    # a half-applied migration must never be left on disk.
    conn.execute("BEGIN IMMEDIATE")
    try:
        while current < SCHEMA_VERSION:
            step = _MIGRATIONS.get(current)
            if step is None:
                raise RuntimeError(f"No migration from schema version {current}.")
            step(conn)
            current += 1
            _write_schema_version(conn, current)
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
    return current
