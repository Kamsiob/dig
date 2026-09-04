"""The one place anything is written.

`write` is the only function that touches a record table, and it always appends
to the oplog in the same transaction, so the log is a complete account of every
change this device has ever made. `save_state` takes the whole document the
interface holds, works out what actually changed, and puts each change through
`write`.

Deletes are tombstones. A record that goes away keeps its row with `deleted`
set, so a device that has been away learns it went rather than bringing it back.
"""

from __future__ import annotations

import json
import os
import platform
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from dig.store import records
from dig.store.schema import SCHEMA_VERSION, SchemaTooNewError, TABLES, ensure

TOMBSTONE_DAYS = 90
HISTORY_KEEP = 20


_COLUMNS: dict[str, frozenset] = {}


def columns_of(conn: sqlite3.Connection, table: str) -> frozenset:
    """What that table actually holds. Read once, then remembered."""
    known = _COLUMNS.get(table)
    if known is None:
        known = frozenset(
            row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        )
        _COLUMNS[table] = known
    return known


@dataclass
class LoadResult:
    state: dict | None
    notice: str = ""
    recovered: bool = False
    meta: dict = field(default_factory=dict)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


class Store:
    """Dig's database."""

    def __init__(self, db_path: Path, history_dir: Path, history_keep: int = HISTORY_KEEP) -> None:
        self.db_path = Path(db_path)
        self.history_dir = Path(history_dir)
        self.history_keep = history_keep
        self._conn: sqlite3.Connection | None = None
        self._device: str | None = None
        # Set when the file is intact but this build must not write to it.
        self.read_only = False

    # ------------------------------------------------------------ connection

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path), isolation_level=None)
            conn.row_factory = sqlite3.Row
            ensure(conn)
            self._conn = conn
            self._ensure_device(conn)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _ensure_device(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT id, name FROM devices WHERE is_self = 1").fetchone()
        if row is None:
            device_id = str(uuid.uuid4())
            try:
                name = platform.node() or "this computer"
            except Exception:
                name = "this computer"
            with conn:
                conn.execute(
                    "INSERT INTO devices (id, name, is_self, paired_at) VALUES (?, ?, 1, ?)",
                    (device_id, name, now_iso()),
                )
            self._device = device_id
        else:
            self._device = row["id"]

    @property
    def device_id(self) -> str:
        self.connect()
        return self._device or ""

    def device_name(self) -> str:
        conn = self.connect()
        row = conn.execute("SELECT name FROM devices WHERE is_self = 1").fetchone()
        return row["name"] if row else ""

    # ----------------------------------------------------------- the one write

    def write(
        self,
        conn: sqlite3.Connection,
        collection: str,
        record_id: str,
        op: str,
        values: dict | None = None,
        device: str | None = None,
        at: str | None = None,
    ) -> int:
        """Update a record and append to the oplog. Nothing else writes records.

        Returns the revision the record is now on. Must be called inside a
        transaction so the row and its log entry land together or not at all.
        """
        if collection not in TABLES:
            raise KeyError(f"no such collection: {collection}")
        device = device or self.device_id
        at = at or now_iso()
        values = dict(values or {})
        values.pop("id", None)
        # Column names go into the statement itself, and a paired device is the
        # one thing that can put a name here that this computer did not choose.
        # Anything that is not a real column of this table is dropped rather
        # than trusted.
        allowed = columns_of(conn, collection)
        unknown = [key for key in values if key not in allowed]
        for key in unknown:
            values.pop(key)

        existing = conn.execute(
            f"SELECT rev, created_at FROM {collection} WHERE id = ?", (record_id,)
        ).fetchone()

        for column in records.JSON_COLUMNS.get(collection, ()):
            if column in values and not isinstance(values[column], str):
                values[column] = json.dumps(values[column])

        if op == "delete":
            if existing is None:
                return 0
            rev = int(existing["rev"]) + 1
            conn.execute(
                f"UPDATE {collection} SET deleted = 1, deleted_at = ?, updated_at = ?,"
                f" updated_by = ?, rev = ? WHERE id = ?",
                (at, at, device, rev, record_id),
            )
        elif existing is None:
            rev = 1
            columns = ["id", "created_at", "updated_at", "updated_by", "rev", "deleted"]
            params = [record_id, at, at, device, rev, 0]
            for key, value in values.items():
                columns.append(key)
                params.append(value)
            placeholders = ", ".join("?" for _ in columns)
            conn.execute(
                f"INSERT INTO {collection} ({', '.join(columns)}) VALUES ({placeholders})",
                params,
            )
            op = "create"
        else:
            rev = int(existing["rev"]) + 1
            sets = ", ".join(f"{key} = ?" for key in values)
            params = list(values.values()) + [at, device, rev, record_id]
            clause = f"{sets}, " if sets else ""
            conn.execute(
                f"UPDATE {collection} SET {clause}deleted = 0, deleted_at = NULL,"
                f" updated_at = ?, updated_by = ?, rev = ? WHERE id = ?",
                params,
            )
            op = "update"

        conn.execute(
            "INSERT INTO oplog (collection, record_id, rev, op, payload, at, device)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (collection, record_id, rev, op, json.dumps(values, default=str), at, device),
        )
        return rev

    # ------------------------------------------------------------------- read

    def _read_rows(self, conn: sqlite3.Connection, include_deleted: bool = False) -> dict:
        out: dict[str, list[dict]] = {}
        for name in records.COLLECTIONS:
            where = "" if include_deleted else " WHERE deleted = 0"
            rows = []
            for row in conn.execute(f"SELECT * FROM {name}{where}"):
                item = dict(row)
                for column in records.JSON_COLUMNS.get(name, ()):
                    try:
                        item[column] = json.loads(item.get(column) or "null")
                    except (TypeError, ValueError):
                        item[column] = None
                rows.append(item)
            out[name] = rows
        return out

    def _read_settings(self, conn: sqlite3.Connection) -> dict:
        out = {}
        for row in conn.execute("SELECT key, value FROM settings"):
            try:
                out[row["key"]] = json.loads(row["value"])
            except (TypeError, ValueError):
                out[row["key"]] = None
        return out

    def load(self) -> LoadResult:
        """Read everything back as the document the interface holds."""
        if not self.db_path.exists():
            return LoadResult(state=None)
        try:
            conn = self.connect()
            rows = self._read_rows(conn)
            settings = self._read_settings(conn)
        except SchemaTooNewError:
            raise
        except (sqlite3.DatabaseError, ValueError) as exc:
            # Only actual corruption earns a recovery. A file Dig merely could
            # not open, because the disk is full or a permission is wrong, is
            # intact and must be left exactly where it is.
            return self._recover(str(exc))
        except OSError as exc:
            return LoadResult(
                state=None,
                notice=(
                    "Dig could not open your data file, so it has not touched it."
                    f" Nothing was changed. ({exc.strerror or exc})"
                ),
            )

        if not settings and not any(rows.values()):
            return LoadResult(state=None, meta=self.meta())
        return LoadResult(state=records.rebuild(rows, settings), meta=self.meta())

    def meta(self) -> dict:
        conn = self.connect()
        cursor = conn.execute("SELECT COALESCE(MAX(seq), 0) AS seq FROM oplog").fetchone()
        return {
            "schema_version": SCHEMA_VERSION,
            "device_id": self.device_id,
            "device_name": self.device_name(),
            "cursor": int(cursor["seq"]) if cursor else 0,
        }

    # ------------------------------------------------------------------ write

    def save_state(self, state: dict, known_cursor: int = 0) -> dict:
        """Work out what changed in the document and put each change through `write`.

        `known_cursor` is how far the oplog had got when the document being
        saved was read out of here. A record another device wrote after that
        point is one this document has never seen, so its absence means nothing
        and it is left alone. Without that, the first save after a sync would
        delete everything that had just arrived. The cursor is used rather than
        a time because the other device's clock is not ours to trust.

        Returns a small summary of what was written, which the tests read.
        """
        if self.read_only:
            raise RuntimeError("This data file was written by a newer Dig.")
        conn = self.connect()
        wanted, settings = records.flatten(state)
        summary = {"created": 0, "updated": 0, "deleted": 0, "kept": 0}
        at = now_iso()
        device = self.device_id

        arrived = {
            (row["collection"], row["record_id"])
            for row in conn.execute(
                "SELECT collection, record_id FROM oplog"
                " WHERE seq > ? AND device != ?", (known_cursor, device)
            ).fetchall()
        }

        with conn:
            current = self._read_rows(conn, include_deleted=True)
            for collection in records.COLLECTIONS:
                have = {row["id"]: row for row in current.get(collection, [])}
                want = {row["id"]: row for row in wanted.get(collection, [])}

                for record_id, values in want.items():
                    row = have.get(record_id)
                    if row is None:
                        self.write(conn, collection, record_id, "create", values, device, at)
                        summary["created"] += 1
                        continue
                    if row.get("deleted") or _changed(row, values, collection):
                        self.write(conn, collection, record_id, "update", values, device, at)
                        summary["updated"] += 1

                for record_id, row in have.items():
                    if record_id in want or row.get("deleted"):
                        continue
                    if (collection, record_id) in arrived:
                        summary["kept"] += 1
                        continue
                    self.write(conn, collection, record_id, "delete", None, device, at)
                    summary["deleted"] += 1

            for key, value in settings.items():
                self._write_setting(conn, key, value, device, at)

        self._snapshot(state)
        return summary

    def _write_setting(self, conn, key: str, value, device: str, at: str) -> None:
        encoded = json.dumps(value, default=str)
        row = conn.execute("SELECT value, rev FROM settings WHERE key = ?", (key,)).fetchone()
        if row is not None and row["value"] == encoded:
            return
        rev = (int(row["rev"]) + 1) if row is not None else 1
        conn.execute(
            "INSERT INTO settings (key, value, updated_at, updated_by, rev) VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at,"
            " updated_by=excluded.updated_by, rev=excluded.rev",
            (key, encoded, at, device, rev),
        )
        conn.execute(
            "INSERT INTO oplog (collection, record_id, rev, op, payload, at, device)"
            " VALUES ('settings', ?, ?, 'update', ?, ?, ?)",
            (key, rev, encoded, at, device),
        )

    # -------------------------------------------------------------- housekeeping

    def changes_since(self, cursor: int, limit: int = 500) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM oplog WHERE seq > ? ORDER BY seq LIMIT ?", (cursor, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    def purge_tombstones(self, acknowledged_by_all: bool = False, days: int = TOMBSTONE_DAYS) -> int:
        """Drop tombstones older than the window, once every device has seen them.

        Never called on its own timer. A tombstone that is still the only thing
        telling another device a record went away must outlive that device's
        absence.
        """
        if not acknowledged_by_all:
            return 0
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn = self.connect()
        removed = 0
        with conn:
            for name in records.COLLECTIONS:
                cur = conn.execute(
                    f"DELETE FROM {name} WHERE deleted = 1 AND deleted_at IS NOT NULL"
                    f" AND deleted_at < ?",
                    (cutoff,),
                )
                removed += cur.rowcount or 0
        return removed

    def update_window(self, geometry: dict) -> None:
        """Remember where the window is, even when nothing else changed."""
        if self.read_only:
            return
        conn = self.connect()
        with conn:
            row = conn.execute("SELECT value FROM settings WHERE key='ui'").fetchone()
            try:
                ui = json.loads(row["value"]) if row else {}
            except (TypeError, ValueError):
                ui = {}
            if not isinstance(ui, dict):
                ui = {}
            if ui.get("window") == geometry:
                return
            ui["window"] = geometry
            self._write_setting(conn, "ui", ui, self.device_id, now_iso())

    def deleted_since(self, days: int = 30) -> list[dict]:
        """What is in Recently deleted: tombstones from the last `days`."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn = self.connect()
        out = []
        for name in records.COLLECTIONS:
            for row in conn.execute(
                f"SELECT * FROM {name} WHERE deleted = 1 AND deleted_at >= ? ORDER BY deleted_at DESC",
                (cutoff,),
            ):
                item = dict(row)
                item["collection"] = name
                out.append(item)
        out.sort(key=lambda r: r.get("deleted_at") or "", reverse=True)
        return out

    # What belongs to a project or a group, and follows it back out of the bin.
    CHILDREN = {
        "projects": (
            ("checklist_items", "project_id"), ("decisions", "project_id"),
            ("releases", "project_id"), ("people", "project_id"),
            ("links", "project_id"), ("stage_history", "project_id"),
            ("wait_history", "project_id"), ("log_entries", "project_id"),
            ("files", "project_id"),
        ),
        "groups": (
            ("links", "group_id"), ("decisions", "group_id"),
            ("log_entries", "group_id"), ("files", "group_id"),
        ),
    }

    def restore(self, collection: str, record_id: str) -> bool:
        """Bring a record back, and everything that belonged to it.

        A project that went in the bin took its checklist, its decisions, its
        files and its log with it, so it comes back with them.
        """
        conn = self.connect()
        row = conn.execute(
            f"SELECT rev FROM {collection} WHERE id = ? AND deleted = 1", (record_id,)
        ).fetchone()
        if row is None:
            return False
        at = now_iso()
        with conn:
            self.write(conn, collection, record_id, "update", {}, self.device_id, at)
            for child, column in self.CHILDREN.get(collection, ()):
                for kid in conn.execute(
                    f"SELECT id FROM {child} WHERE {column} = ? AND deleted = 1", (record_id,)
                ).fetchall():
                    self.write(conn, child, kid["id"], "update", {}, self.device_id, at)
        return True

    # ------------------------------------------------------------ the history

    def _snapshot(self, state: dict) -> None:
        try:
            self.history_dir.mkdir(parents=True, exist_ok=True)
            target = self.history_dir / f"state-{_stamp()}.json"
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=str(self.history_dir),
                prefix=".state-", suffix=".tmp", delete=False,
            ) as handle:
                json.dump(state, handle, default=str)
                handle.flush()
                os.fsync(handle.fileno())
                staged = Path(handle.name)
            os.replace(str(staged), str(target))
            for old in self.history_files()[self.history_keep:]:
                old.unlink(missing_ok=True)
        except OSError:
            pass  # history is a convenience, never a reason to lose a save

    def history_files(self) -> list[Path]:
        if not self.history_dir.is_dir():
            return []
        files = [p for p in self.history_dir.glob("state-*.json") if p.is_file()]
        return sorted(files, key=lambda p: p.name, reverse=True)

    def _recover(self, why: str = "") -> LoadResult:
        self.close()
        broken = self.db_path.with_name(f"{self.db_path.name}.broken-{_stamp()}")
        try:
            os.replace(str(self.db_path), str(broken))
        except OSError:
            broken = self.db_path
        for extra in (".wal", "-wal", "-shm"):
            sibling = self.db_path.with_name(self.db_path.name + extra)
            if sibling.exists():
                sibling.unlink(missing_ok=True)

        for snapshot in self.history_files():
            try:
                state = json.loads(snapshot.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(state, dict):
                continue
            self.save_state(state)
            return LoadResult(
                state=self.load().state,
                recovered=True,
                meta=self.meta(),
                notice=(
                    "Your data file could not be read. Dig went back to the last good"
                    f" save from {_readable(snapshot)}. The unreadable file is kept as"
                    f" {broken.name}."
                ),
            )

        return LoadResult(
            state=None,
            recovered=True,
            meta=self.meta(),
            notice=(
                "Your data file could not be read and there was no earlier save to go"
                f" back to. Dig started fresh. The unreadable file is kept as {broken.name}."
            ),
        )


def _changed(row: dict, values: dict, collection: str) -> bool:
    for key, value in values.items():
        have = row.get(key)
        if key in records.JSON_COLUMNS.get(collection, ()):
            if have != value:
                return True
            continue
        if isinstance(value, bool):
            value = 1 if value else 0
        if have != value:
            return True
    return False


def _readable(snapshot: Path) -> str:
    try:
        stem = snapshot.stem.split("state-", 1)[1]
        when = datetime.strptime(stem[:15], "%Y%m%d-%H%M%S")
    except (IndexError, ValueError):
        return "an earlier point"
    return when.strftime("%b %-d at %-I:%M %p")
