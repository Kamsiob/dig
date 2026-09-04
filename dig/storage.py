"""The state document store.

Dig keeps its whole state as one JSON document in a single row of a SQLite
file. Every save writes a complete new database to a temporary file, flushes it
to disk, and renames it over the real one, so a save is either fully there or
not there at all. Alongside it a rolling set of the last twenty saves is kept as
plain JSON, which is what recovery reads when the database cannot be opened.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 2
HISTORY_KEEP = 20

_CREATE_STATE = (
    "CREATE TABLE IF NOT EXISTS state ("
    " id INTEGER PRIMARY KEY CHECK(id=1),"
    " json TEXT NOT NULL,"
    " schema_version INTEGER NOT NULL,"
    " updated_at TEXT NOT NULL)"
)


class StateTooNewError(RuntimeError):
    """The file was written by a newer Dig. It is intact, so never set it aside."""


@dataclass
class LoadResult:
    """What came back from a load, and anything the person needs told."""

    state: dict | None
    notice: str = ""
    recovered: bool = False


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def _fsync_dir(path: Path) -> None:
    """Flush a directory entry so a rename survives a power cut."""
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    except OSError:
        pass  # some filesystems do not allow fsync on a directory
    finally:
        os.close(fd)


class StateStore:
    """Reads and writes the one state document."""

    def __init__(
        self,
        db_path: Path,
        history_dir: Path,
        history_keep: int = HISTORY_KEEP,
    ) -> None:
        self.db_path = Path(db_path)
        self.history_dir = Path(history_dir)
        self.history_keep = history_keep

    # ----------------------------------------------------------------- write

    def save(self, payload: str) -> None:
        """Write the document. Atomic: temp file, fsync, rename.

        `payload` is already-serialized JSON. It is parsed once to be sure a
        broken document never reaches the file.
        """
        json.loads(payload)  # refuse to persist anything unreadable
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        tmp = self.db_path.with_name(
            f"{self.db_path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        )
        try:
            conn = sqlite3.connect(str(tmp))
            try:
                conn.execute("PRAGMA journal_mode=DELETE")
                conn.execute(_CREATE_STATE)
                conn.execute(
                    "INSERT INTO state (id, json, schema_version, updated_at)"
                    " VALUES (1, ?, ?, ?)"
                    " ON CONFLICT(id) DO UPDATE SET json=excluded.json,"
                    " schema_version=excluded.schema_version,"
                    " updated_at=excluded.updated_at",
                    (payload, SCHEMA_VERSION, datetime.now().isoformat(timespec="seconds")),
                )
                conn.commit()
            finally:
                conn.close()

            fd = os.open(str(tmp), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

            os.replace(str(tmp), str(self.db_path))
            _fsync_dir(self.db_path.parent)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

        self._snapshot(payload)

    def _snapshot(self, payload: str) -> None:
        """Keep the newest `history_keep` saves as timestamped JSON."""
        try:
            self.history_dir.mkdir(parents=True, exist_ok=True)
            target = self.history_dir / f"state-{_stamp()}.json"
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=str(self.history_dir),
                prefix=".state-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                staged = Path(handle.name)
            os.replace(str(staged), str(target))
            self._trim_history()
        except OSError:
            pass  # history is a convenience, never a reason to lose a save

    def _trim_history(self) -> None:
        files = self.history_files()
        for old in files[self.history_keep :]:
            old.unlink(missing_ok=True)

    def history_files(self) -> list[Path]:
        """History snapshots, newest first."""
        if not self.history_dir.is_dir():
            return []
        files = [p for p in self.history_dir.glob("state-*.json") if p.is_file()]
        return sorted(files, key=lambda p: p.name, reverse=True)

    # ------------------------------------------------------------------ read

    def load(self) -> LoadResult:
        """Read the document, recovering from history if the file is broken."""
        if not self.db_path.exists():
            return LoadResult(state=None)

        try:
            return LoadResult(state=self._read_db())
        except StateTooNewError:
            raise
        except Exception:
            return self._recover()

    def _read_db(self) -> dict:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT json, schema_version FROM state WHERE id = 1"
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise ValueError("no state row")
        version = int(row[1])
        if version > SCHEMA_VERSION:
            raise StateTooNewError(
                f"This file was written by a newer Dig (format {version})."
            )
        state = json.loads(row[0])
        if not isinstance(state, dict):
            raise ValueError("state is not an object")
        return state

    def _recover(self) -> LoadResult:
        """Set the unreadable file aside and fall back to the newest good save."""
        broken = self.db_path.with_name(f"{self.db_path.name}.broken-{_stamp()}")
        try:
            os.replace(str(self.db_path), str(broken))
        except OSError:
            broken = self.db_path

        for snapshot in self.history_files():
            try:
                state = json.loads(snapshot.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(state, dict):
                continue
            when = _readable_time(snapshot)
            return LoadResult(
                state=state,
                recovered=True,
                notice=(
                    f"Your data file could not be read. Dig went back to the last"
                    f" good save from {when}. The unreadable file is kept as"
                    f" {broken.name}."
                ),
            )

        return LoadResult(
            state=None,
            recovered=True,
            notice=(
                "Your data file could not be read and there was no earlier save to"
                f" go back to. Dig started fresh. The unreadable file is kept as"
                f" {broken.name}."
            ),
        )


def _readable_time(snapshot: Path) -> str:
    """Turn state-20260904-141500-000000.json into `Sep 4 at 2:15 PM`."""
    try:
        stem = snapshot.stem.split("state-", 1)[1]
        when = datetime.strptime(stem[:15], "%Y%m%d-%H%M%S")
    except (IndexError, ValueError):
        return "an earlier point"
    return when.strftime("%b %-d at %-I:%M %p")
