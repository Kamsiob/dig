"""How two devices agree on what happened.

Every record carries when it last changed and which device changed it, so a
change arriving from somewhere else can be judged against what is here without
either side having to be right by default.

The rules, in order:

1. A record we have never seen is simply taken.
2. A delete beats a concurrent edit. The tombstone wins, and the edit that lost
   is written to the conflicts table rather than thrown away.
3. An edit arriving for something already deleted here does not resurrect it.
   It goes to conflicts too.
4. Otherwise the later `updated_at` wins, field by field, with the device id
   breaking a tie so both sides reach the same answer.

A change that has already been applied, the same device at the same instant, is
ignored rather than written again, so a batch that arrives twice does not bounce
back and forth between two devices forever.

Nothing here opens a socket. It is the part worth testing on its own.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from dig.store import records
from dig.store.store import now_iso

ACCEPTED = "accepted"
CONFLICT = "conflict"
IGNORED = "ignored"


@dataclass
class Outcome:
    record_id: str
    collection: str
    result: str
    why: str = ""


def newer(a_at: str, a_device: str, b_at: str, b_device: str) -> bool:
    """Whether A is the later change. The device id only breaks an exact tie."""
    if (a_at or "") != (b_at or ""):
        return (a_at or "") > (b_at or "")
    return (a_device or "") > (b_device or "")


def _row(conn, collection: str, record_id: str):
    try:
        return conn.execute(
            f"SELECT * FROM {collection} WHERE id = ?", (record_id,)
        ).fetchone()
    except Exception:
        return None


def _record_conflict(conn, collection: str, record_id: str, device: str, why: str, losing) -> None:
    conn.execute(
        "INSERT INTO conflicts (id, collection, record_id, at, device, reason, losing, seen)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
        (
            str(uuid.uuid4()), collection, record_id, now_iso(), device, why,
            json.dumps(losing, default=str),
        ),
    )


def apply_change(store, conn, change: dict) -> Outcome:
    """Take one change from another device, or say why it was not taken."""
    collection = change.get("collection")
    record_id = change.get("record_id")
    op = change.get("op")
    device = change.get("device") or "unknown"
    at = change.get("at") or now_iso()

    if collection == "settings":
        return _apply_setting(conn, change, device, at)
    if collection not in records.COLLECTIONS or not record_id:
        return Outcome(record_id or "", collection or "", IGNORED, "no such collection")

    payload = change.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            payload = {}
    payload = payload or {}

    mine = _row(conn, collection, record_id)

    # 1. Never seen it.
    if mine is None:
        if op == "delete":
            store.write(conn, collection, record_id, "create", {}, device, at)
            store.write(conn, collection, record_id, "delete", None, device, at)
        else:
            store.write(conn, collection, record_id, "create", payload, device, at)
        return Outcome(record_id, collection, ACCEPTED)

    mine_at = mine["updated_at"] or ""
    mine_by = mine["updated_by"] or ""

    # Already applied. The same device, at the same instant, is the same change
    # arriving again, and applying it twice would bounce it back and forth.
    if mine_at == at and mine_by == device and bool(mine["deleted"]) == (op == "delete"):
        return Outcome(record_id, collection, IGNORED, "already applied")

    # 2. A delete beats a concurrent edit.
    if op == "delete":
        if not mine["deleted"] and newer(mine_at, mine_by, at, device):
            _record_conflict(
                conn, collection, record_id, device,
                "deleted elsewhere while it was being edited here", dict(mine),
            )
        store.write(conn, collection, record_id, "delete", None, device, at)
        return Outcome(record_id, collection, ACCEPTED)

    # 3. An edit does not undo a delete.
    if mine["deleted"]:
        _record_conflict(
            conn, collection, record_id, device,
            "edited elsewhere after it was deleted here", payload,
        )
        return Outcome(record_id, collection, CONFLICT, "already deleted here")

    # 4. The later change wins.
    if newer(mine_at, mine_by, at, device):
        return Outcome(record_id, collection, IGNORED, "what is here is newer")

    store.write(conn, collection, record_id, "update", payload, device, at)
    return Outcome(record_id, collection, ACCEPTED)


def _apply_setting(conn, change: dict, device: str, at: str) -> Outcome:
    key = change.get("record_id") or ""
    payload = change.get("payload")
    if not isinstance(payload, str):
        payload = json.dumps(payload, default=str)
    row = conn.execute("SELECT value, updated_at, updated_by, rev FROM settings WHERE key = ?", (key,)).fetchone()
    if row is not None:
        if (row["updated_at"] or "") == at and (row["updated_by"] or "") == device:
            return Outcome(key, "settings", IGNORED, "already applied")
        if newer(row["updated_at"] or "", row["updated_by"] or "", at, device):
            return Outcome(key, "settings", IGNORED, "what is here is newer")
    rev = (int(row["rev"]) + 1) if row is not None else 1
    conn.execute(
        "INSERT INTO settings (key, value, updated_at, updated_by, rev) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at,"
        " updated_by=excluded.updated_by, rev=excluded.rev",
        (key, payload, at, device, rev),
    )
    conn.execute(
        "INSERT INTO oplog (collection, record_id, rev, op, payload, at, device)"
        " VALUES ('settings', ?, ?, 'update', ?, ?, ?)",
        (key, rev, payload, at, device),
    )
    return Outcome(key, "settings", ACCEPTED)


def apply_batch(store, changes: list) -> list:
    """Take a batch in one transaction, and say what happened to each."""
    conn = store.connect()
    out = []
    with conn:
        for change in changes:
            try:
                out.append(apply_change(store, conn, change))
            except Exception as exc:
                out.append(
                    Outcome(
                        change.get("record_id", ""), change.get("collection", ""),
                        IGNORED, str(exc)[:120],
                    )
                )
    return out


def open_conflicts(store) -> list:
    conn = store.connect()
    rows = conn.execute(
        "SELECT * FROM conflicts WHERE seen = 0 ORDER BY at DESC LIMIT 200"
    ).fetchall()
    return [dict(r) for r in rows]


def mark_conflicts_seen(store, ids: list) -> int:
    conn = store.connect()
    with conn:
        for one in ids:
            conn.execute("UPDATE conflicts SET seen = 1 WHERE id = ?", (one,))
    return len(ids)
