"""The one way in and out of Dig's data.

Every read and write the interface needs lives here. Nothing above this layer
touches SQL or the filesystem directly. Every write runs in a transaction.
"""

from __future__ import annotations

import random
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from dig import paths
from dig.storage import schema
from dig.storage.models import (
    BUG,
    FEATURE,
    KINDS,
    App,
    Attachment,
    Idea,
    SheetCounts,
    SheetItem,
)

IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".svg",
    ".avif",
}

RECENT_COUNT = 3
"""How many ideas Home shows under Recent. The unearth pool starts below these."""


def utcnow_iso() -> str:
    """Current time as a sortable UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def looks_like_an_image(name: str) -> bool:
    return Path(name).suffix.lower() in IMAGE_SUFFIXES


def split_jot(raw: str) -> tuple[str, str]:
    """First line becomes the title, everything after it becomes the note."""
    text = (raw or "").strip()
    if not text:
        return "", ""
    head, _, tail = text.partition("\n")
    return head.strip(), tail.strip()


class StoreError(RuntimeError):
    """Something went wrong that the interface should tell the user about."""


class Store:
    """Dig's data layer, backed by SQLite."""

    def __init__(self, db_file: Path | None = None, attachments_root: Path | None = None):
        self._db_file = Path(db_file) if db_file else paths.db_path()
        self._attachments_root = (
            Path(attachments_root) if attachments_root else paths.attachments_dir()
        )
        self.recovery_notice: str | None = None
        """Set when a broken database was set aside and a fresh one started."""
        self._conn: sqlite3.Connection | None = None
        self._savepoint_depth = 0

    # ---------- lifecycle ----------

    @property
    def db_file(self) -> Path:
        return self._db_file

    @property
    def attachments_root(self) -> Path:
        return self._attachments_root

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise StoreError("The data store is not open.")
        return self._conn

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        """Run a write inside a real transaction.

        The connection is in autocommit mode, so transactions are opened by
        hand: `with conn` alone would neither begin one nor roll anything back.
        Nested writes use savepoints so a compound operation such as promoting
        an idea commits or fails as a single unit.
        """
        conn = self.conn
        if conn.in_transaction:
            name = f"dig_sp_{self._savepoint_depth}"
            self._savepoint_depth += 1
            conn.execute(f"SAVEPOINT {name}")
            try:
                yield conn
            except BaseException:
                conn.execute(f"ROLLBACK TO {name}")
                conn.execute(f"RELEASE {name}")
                raise
            else:
                conn.execute(f"RELEASE {name}")
            finally:
                self._savepoint_depth -= 1
        else:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")

    def open(self) -> Store:
        """Open the database, recovering from a corrupt file if needed."""
        self._db_file.parent.mkdir(parents=True, exist_ok=True)
        self._attachments_root.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = self._connect()
            schema.migrate(self._conn)
        except schema.SchemaTooNewError:
            # Intact data from a newer Dig. Say so plainly; never set it aside.
            self.close()
            raise
        except (sqlite3.DatabaseError, RuntimeError) as first_error:
            self._set_aside_broken_database(first_error)
            self._conn = self._connect()
            schema.migrate(self._conn)
        return self

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_file, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA synchronous = NORMAL")
        # Touch the file so an unreadable database fails here, not mid-session.
        conn.execute("PRAGMA quick_check").fetchone()
        return conn

    def _set_aside_broken_database(self, cause: Exception) -> None:
        """Move an unreadable database aside and start fresh.

        Nothing is deleted: the bad file stays next to the new one so it can be
        inspected or recovered by hand later.
        """
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        if self._db_file.exists():
            broken = self._db_file.with_name(f"{self._db_file.name}.broken-{stamp}")
            counter = 2
            while broken.exists():
                broken = self._db_file.with_name(
                    f"{self._db_file.name}.broken-{stamp}-{counter}"
                )
                counter += 1
            shutil.move(str(self._db_file), str(broken))
            # The write-ahead log belongs to the old file; it cannot be replayed.
            for sidecar in ("-wal", "-shm"):
                stray = self._db_file.with_name(self._db_file.name + sidecar)
                if stray.exists():
                    stray.unlink()
            self.recovery_notice = (
                f"Dig could not read its database, so it started a fresh one. "
                f"The unreadable file is kept at {broken.name} in the data folder."
            )
        else:
            self.recovery_notice = (
                "Dig could not open its database, so it started a fresh one."
            )
        _ = cause  # kept for callers that want to log it

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> Store:
        return self.open()

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ---------- ideas ----------

    def create_idea(self, raw_text: str) -> Idea | None:
        """Save a jot. Empty or whitespace-only input saves nothing."""
        title, note = split_jot(raw_text)
        if not title:
            return None
        now = utcnow_iso()
        with self._write():
            cur = self.conn.execute(
                "INSERT INTO ideas (title, note, created_at) VALUES (?, ?, ?)",
                (title, note, now),
            )
        return self.get_idea(int(cur.lastrowid))

    def get_idea(self, idea_id: int) -> Idea | None:
        row = self.conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,)).fetchone()
        return _idea(row) if row else None

    def update_idea(self, idea_id: int, title: str, note: str) -> None:
        with self._write():
            self.conn.execute(
                "UPDATE ideas SET title = ?, note = ? WHERE id = ?",
                (title.strip(), note.strip(), idea_id),
            )

    def delete_idea(self, idea_id: int) -> None:
        with self._write():
            self.conn.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))

    def mark_idea_opened(self, idea_id: int) -> None:
        """Stamp the moment an idea was last dug up and looked at."""
        with self._write():
            self.conn.execute(
                "UPDATE ideas SET last_opened_at = ? WHERE id = ?",
                (utcnow_iso(), idea_id),
            )

    def list_ideas(
        self,
        include_promoted: bool = False,
        search: str = "",
        limit: int | None = None,
    ) -> list[Idea]:
        """Ideas newest first. Promoted ones are out of the way unless asked for."""
        sql = "SELECT * FROM ideas"
        clauses: list[str] = []
        args: list[object] = []
        if not include_promoted:
            clauses.append("promoted_app_id IS NULL")
        term = (search or "").strip()
        if term:
            clauses.append("(title LIKE ? OR note LIKE ?)")
            pattern = f"%{term}%"
            args += [pattern, pattern]
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC, id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            args.append(limit)
        return [_idea(r) for r in self.conn.execute(sql, args).fetchall()]

    def recent_ideas(self, limit: int = RECENT_COUNT) -> list[Idea]:
        """The newest unpromoted ideas — what Home shows under Recent."""
        return self.list_ideas(limit=limit)

    def unearth_candidates(
        self, recent_count: int = RECENT_COUNT, exclude_id: int | None = None
    ) -> list[Idea]:
        """Everything old enough to unearth: unpromoted, below the Recent rows."""
        sql = (
            "SELECT * FROM ideas WHERE promoted_app_id IS NULL "
            "ORDER BY created_at DESC, id DESC LIMIT -1 OFFSET ?"
        )
        rows = self.conn.execute(sql, (recent_count,)).fetchall()
        pool = [_idea(r) for r in rows]
        if exclude_id is not None:
            pool = [i for i in pool if i.id != exclude_id]
        return pool

    def unearth(
        self, recent_count: int = RECENT_COUNT, exclude_id: int | None = None
    ) -> Idea | None:
        """Pull one idea out of the ground at random. None when nothing qualifies."""
        pool = self.unearth_candidates(recent_count, exclude_id)
        if not pool:
            return None
        return random.choice(pool)

    # ---------- apps ----------

    def create_app(
        self,
        name: str,
        description: str = "",
        github_url: str = "",
        version_label: str = "",
        shipped: bool = False,
        notes: str = "",
        origin_idea_id: int | None = None,
    ) -> App:
        clean = (name or "").strip()
        if not clean:
            raise StoreError("An app needs a name.")
        now = utcnow_iso()
        with self._write():
            cur = self.conn.execute(
                "INSERT INTO apps (name, description, notes, github_url, "
                "version_label, shipped, origin_idea_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    clean,
                    (description or "").strip(),
                    notes or "",
                    (github_url or "").strip(),
                    (version_label or "").strip(),
                    1 if shipped else 0,
                    origin_idea_id,
                    now,
                ),
            )
        app = self.get_app(int(cur.lastrowid))
        assert app is not None
        return app

    def get_app(self, app_id: int) -> App | None:
        row = self.conn.execute("SELECT * FROM apps WHERE id = ?", (app_id,)).fetchone()
        return _app(row) if row else None

    def list_apps(self) -> list[App]:
        """Apps in alphabetical order — the order every picker uses."""
        rows = self.conn.execute(
            "SELECT * FROM apps ORDER BY name COLLATE NOCASE ASC, id ASC"
        ).fetchall()
        return [_app(r) for r in rows]

    def update_app(self, app_id: int, **fields: object) -> None:
        """Update any subset of an app's columns."""
        allowed = {
            "name",
            "description",
            "notes",
            "github_url",
            "version_label",
            "shipped",
        }
        sets: list[str] = []
        args: list[object] = []
        for key, value in fields.items():
            if key not in allowed:
                raise StoreError(f"Cannot update unknown app field '{key}'.")
            if key == "shipped":
                value = 1 if value else 0
            elif isinstance(value, str) and key != "notes":
                value = value.strip()
            sets.append(f"{key} = ?")
            args.append(value)
        if not sets:
            return
        args.append(app_id)
        with self._write():
            self.conn.execute(f"UPDATE apps SET {', '.join(sets)} WHERE id = ?", args)

    def forget_app(self, app_id: int) -> Path:
        """Delete an app and everything hanging off it in the database.

        Returns the attachment folder, which is still on disk. Database only,
        so the caller can clear the folder on a worker thread afterwards.
        """
        folder = self.app_attachments_dir(app_id)
        with self._write():
            self.conn.execute("DELETE FROM apps WHERE id = ?", (app_id,))
        return folder

    @staticmethod
    def discard_folder(folder: Path | str) -> None:
        """Remove a stored attachment folder. Filesystem only."""
        path = Path(folder)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)

    def delete_app(self, app_id: int) -> None:
        """Delete an app, its sheets, its attachment rows, and its stored files."""
        self.discard_folder(self.forget_app(app_id))

    def promote_idea(
        self,
        idea_id: int,
        name: str,
        description: str = "",
        github_url: str = "",
        version_label: str = "",
        shipped: bool = False,
    ) -> App:
        """Turn an idea into an app, keeping the thread between them intact.

        The idea leaves the idea pools but is never destroyed: it stays as the
        app's origin and remains visible under "Show promoted".
        """
        idea = self.get_idea(idea_id)
        if idea is None:
            raise StoreError("That idea is no longer here.")
        if idea.is_promoted:
            raise StoreError("That idea has already been made into an app.")
        # Creating the app and linking the idea to it is one indivisible step:
        # an app without its origin, or an idea pointing at nothing, is worse
        # than the promote simply not happening.
        with self._write():
            app = self.create_app(
                name=name,
                description=description,
                github_url=github_url,
                version_label=version_label,
                shipped=shipped,
                origin_idea_id=idea_id,
            )
            self.conn.execute(
                "UPDATE ideas SET promoted_app_id = ? WHERE id = ?", (app.id, idea_id)
            )
        return app

    # ---------- sheets ----------

    def add_sheet_item(self, app_id: int, kind: str, text: str) -> SheetItem | None:
        """Add one line to a sheet. Empty text adds nothing."""
        if kind not in KINDS:
            raise StoreError(f"A sheet item is a feature or a bug, not '{kind}'.")
        clean = (text or "").strip()
        if not clean:
            return None
        with self._write():
            cur = self.conn.execute(
                "INSERT INTO sheet_items (app_id, kind, text, created_at) "
                "VALUES (?, ?, ?, ?)",
                (app_id, kind, clean, utcnow_iso()),
            )
        return self.get_sheet_item(int(cur.lastrowid))

    def get_sheet_item(self, item_id: int) -> SheetItem | None:
        row = self.conn.execute(
            "SELECT * FROM sheet_items WHERE id = ?", (item_id,)
        ).fetchone()
        return _sheet_item(row) if row else None

    def list_sheet_items(self, app_id: int, kind: str) -> list[SheetItem]:
        """Open items newest first, then done items with the latest finish on top."""
        if kind not in KINDS:
            raise StoreError(f"A sheet is features or bugs, not '{kind}'.")
        rows = self.conn.execute(
            "SELECT * FROM sheet_items WHERE app_id = ? AND kind = ? "
            "ORDER BY done ASC, COALESCE(done_at, created_at) DESC, id DESC",
            (app_id, kind),
        ).fetchall()
        return [_sheet_item(r) for r in rows]

    def set_sheet_item_done(self, item_id: int, done: bool) -> None:
        with self._write():
            self.conn.execute(
                "UPDATE sheet_items SET done = ?, done_at = ? WHERE id = ?",
                (1 if done else 0, utcnow_iso() if done else None, item_id),
            )

    def toggle_sheet_item(self, item_id: int) -> bool:
        """Flip an item between done and not done. Returns the new state."""
        item = self.get_sheet_item(item_id)
        if item is None:
            raise StoreError("That line is no longer here.")
        self.set_sheet_item_done(item_id, not item.done)
        return not item.done

    def update_sheet_item_text(self, item_id: int, text: str) -> None:
        clean = (text or "").strip()
        if not clean:
            return
        with self._write():
            self.conn.execute(
                "UPDATE sheet_items SET text = ? WHERE id = ?", (clean, item_id)
            )

    def delete_sheet_item(self, item_id: int) -> None:
        with self._write():
            self.conn.execute("DELETE FROM sheet_items WHERE id = ?", (item_id,))

    def sheet_counts(self, app_id: int, kind: str) -> SheetCounts:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(done = 0), 0) AS open_n, "
            "       COALESCE(SUM(done = 1), 0) AS done_n "
            "FROM sheet_items WHERE app_id = ? AND kind = ?",
            (app_id, kind),
        ).fetchone()
        return SheetCounts(open=int(row["open_n"]), done=int(row["done_n"]))

    def open_counts(self, app_id: int) -> tuple[int, int]:
        """(open features, open bugs) — what the Apps list shows per row."""
        return (
            self.sheet_counts(app_id, FEATURE).open,
            self.sheet_counts(app_id, BUG).open,
        )

    # ---------- attachments ----------

    def app_attachments_dir(self, app_id: int) -> Path:
        return self._attachments_root / str(app_id)

    def stage_attachment(self, app_id: int, source: Path | str) -> Path:
        """Copy a file into the managed folder and return where it landed.

        Filesystem only, touching no database, so it is safe to run on a
        worker thread: a sqlite3 connection belongs to the thread that opened
        it. The original is never moved or altered, and a name already in use
        gets a -2, -3 suffix rather than overwriting what is there.
        """
        src = Path(source).expanduser()
        if not src.is_file():
            raise StoreError(f"There is no file at {src}.")
        folder = self.app_attachments_dir(app_id)
        folder.mkdir(parents=True, exist_ok=True)

        target = _free_path(folder, src.name)
        shutil.copy2(src, target)
        return target

    def record_attachment(self, app_id: int, stored: Path | str) -> Attachment:
        """Record a file already copied into the managed folder."""
        target = Path(stored)
        if not target.is_file():
            raise StoreError(f"There is no stored file at {target}.")
        with self._write():
            cur = self.conn.execute(
                "INSERT INTO attachments (app_id, filename, stored_path, size, "
                "is_image, added_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    app_id,
                    target.name,
                    str(target),
                    target.stat().st_size,
                    1 if looks_like_an_image(target.name) else 0,
                    utcnow_iso(),
                ),
            )
        attachment = self.get_attachment(int(cur.lastrowid))
        assert attachment is not None
        return attachment

    def attach_file(self, app_id: int, source: Path | str) -> Attachment:
        """Copy a file in and record it, in one step."""
        return self.record_attachment(app_id, self.stage_attachment(app_id, source))

    def get_attachment(self, attachment_id: int) -> Attachment | None:
        row = self.conn.execute(
            "SELECT * FROM attachments WHERE id = ?", (attachment_id,)
        ).fetchone()
        return _attachment(row) if row else None

    def list_attachments(
        self, app_id: int, images: bool | None = None
    ) -> list[Attachment]:
        """Attachments oldest first. `images=True` for screenshots, False for files."""
        sql = "SELECT * FROM attachments WHERE app_id = ?"
        args: list[object] = [app_id]
        if images is not None:
            sql += " AND is_image = ?"
            args.append(1 if images else 0)
        sql += " ORDER BY added_at ASC, id ASC"
        return [_attachment(r) for r in self.conn.execute(sql, args).fetchall()]

    def delete_attachment(self, attachment_id: int) -> None:
        """Remove the record and the stored copy together."""
        attachment = self.get_attachment(attachment_id)
        if attachment is None:
            return
        with self._write():
            self.conn.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        stored = Path(attachment.stored_path)
        if stored.is_file():
            try:
                stored.unlink()
            except OSError:
                pass  # the row is gone; a stray file is not worth an error

    # ---------- settings ----------

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._write():
            self.conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )


# ---------- row mapping ----------


def _free_path(folder: Path, filename: str) -> Path:
    """A path in `folder` that nothing occupies, suffixing -2, -3 as needed."""
    candidate = folder / filename
    if not candidate.exists():
        return candidate
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 2
    while True:
        candidate = folder / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _idea(row: sqlite3.Row) -> Idea:
    return Idea(
        id=row["id"],
        title=row["title"],
        note=row["note"],
        created_at=row["created_at"],
        last_opened_at=row["last_opened_at"],
        promoted_app_id=row["promoted_app_id"],
    )


def _app(row: sqlite3.Row) -> App:
    return App(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        notes=row["notes"],
        github_url=row["github_url"],
        version_label=row["version_label"],
        shipped=bool(row["shipped"]),
        origin_idea_id=row["origin_idea_id"],
        created_at=row["created_at"],
    )


def _sheet_item(row: sqlite3.Row) -> SheetItem:
    return SheetItem(
        id=row["id"],
        app_id=row["app_id"],
        kind=row["kind"],
        text=row["text"],
        done=bool(row["done"]),
        created_at=row["created_at"],
        done_at=row["done_at"],
    )


def _attachment(row: sqlite3.Row) -> Attachment:
    return Attachment(
        id=row["id"],
        app_id=row["app_id"],
        filename=row["filename"],
        stored_path=row["stored_path"],
        size=row["size"],
        is_image=bool(row["is_image"]),
        added_at=row["added_at"],
    )
