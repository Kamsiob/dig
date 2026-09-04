"""Bringing Dig v1's data into v2.

v1 kept a normalized database: ideas, apps, per-app feature and bug sheets, and
managed attachments. v2 keeps one JSON document. This runs once, on the first
launch that finds a v1 file, and is described in full in docs/V2_MIGRATION.md.

If anything goes wrong the v1 file is left exactly where it is and nothing is
deleted. A failed migration never costs the person their data.
"""

from __future__ import annotations

import json
import os
import pwd
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dig import paths
from dig.bridge import file_chip, human_size
from dig.storage import StateStore

APPS_GROUP = {"id": "apps", "name": "Apps", "color": "#0BA39E", "priv": False}

APP_TYPE = {
    "id": "app",
    "name": "App",
    "stages": ["Idea", "Plan", "Design", "Build", "Test", "Release", "Keep up"],
    "check": {
        "Plan": ["Write the spec"],
        "Design": ["Approve the mockup", "Write DESIGN.md"],
        "Build": ["Make the repo public", "Keep HANDOFF.md current"],
        "Test": ["Test on a real device"],
        "Release": ["Store listing live", "Publish the release post"],
        "Keep up": ["Review the bug list"],
    },
}

SHIPPED_STAGE = 6  # Keep up, the last App stage
BUILDING_STAGE = 3  # Build, which is what v1 actually tracked


def looks_like_v1(db_path: Path) -> bool:
    """A v1 file has apps and no state. A v2 file has state."""
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    except sqlite3.Error:
        return False
    finally:
        conn.close()
    return "apps" in names and "state" not in names


def _owner_name() -> str:
    """The person's own name if the system knows it."""
    try:
        gecos = pwd.getpwuid(os.getuid()).pw_gecos or ""
    except (KeyError, OSError):
        gecos = ""
    name = gecos.split(",")[0].strip()
    return name or "Your projects"


def _iso(value) -> str:
    """v1 wrote ISO timestamps. Anything unreadable becomes now."""
    text = (value or "").strip() if isinstance(value, str) else ""
    if not text:
        return datetime.now().isoformat()
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now().isoformat()
    return text


def _short_date(value: str) -> str:
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if when.tzinfo is not None:
        when = when.astimezone(timezone.utc).replace(tzinfo=None)
    return when.strftime("%b %-d")


def read_v1(db_path: Path) -> dict:
    """Everything v1 was holding, as plain Python."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        settings = {
            row["key"]: row["value"] for row in conn.execute("SELECT * FROM settings")
        }
        ideas = [dict(row) for row in conn.execute("SELECT * FROM ideas ORDER BY id")]
        apps = [dict(row) for row in conn.execute("SELECT * FROM apps ORDER BY id")]
        items = [
            dict(row) for row in conn.execute("SELECT * FROM sheet_items ORDER BY id")
        ]
        files = [
            dict(row) for row in conn.execute("SELECT * FROM attachments ORDER BY id")
        ]
    finally:
        conn.close()
    return {
        "settings": settings,
        "ideas": ideas,
        "apps": apps,
        "items": items,
        "files": files,
    }


def build_state(v1: dict, move_files: bool = True) -> dict:
    """Turn what v1 held into the v2 document."""
    theme = v1["settings"].get("appearance", "system")
    if theme not in {"light", "dark", "system"}:
        theme = "system"

    owner = _owner_name()
    idea_titles = {row["id"]: row["title"] for row in v1["ideas"]}

    items_by_app: dict[int, list] = {}
    for row in v1["items"]:
        items_by_app.setdefault(row["app_id"], []).append(row)
    files_by_app: dict[int, list] = {}
    for row in v1["files"]:
        files_by_app.setdefault(row["app_id"], []).append(row)

    projects = []
    for app in v1["apps"]:
        pid = f"v1a{app['id']}"
        created = _iso(app.get("created_at"))
        shipped = bool(app.get("shipped"))

        notes = (app.get("notes") or "").strip()
        if not notes:
            notes = (app.get("description") or "").strip()

        links = []
        if (app.get("github_url") or "").strip():
            links.append(app["github_url"].strip())

        checklist = []
        for row in items_by_app.get(app["id"], []):
            checklist.append(
                {
                    "id": f"v1s{row['id']}",
                    "text": row["text"],
                    "done": bool(row["done"]),
                    "tag": "bug" if row["kind"] == "bug" else "",
                }
            )

        files = []
        for row in files_by_app.get(app["id"], []):
            stored = _rehome(row["stored_path"], app["id"], pid) if move_files else row["stored_path"]
            size = human_size(int(row.get("size") or 0))
            when = _short_date(_iso(row.get("added_at")))
            files.append(
                {
                    "type": file_chip(row["filename"]),
                    "name": row["filename"],
                    "meta": f"{size} · {when}" if when else size,
                    "stored_path": stored,
                }
            )

        releases = []
        label = (app.get("version_label") or "").strip()
        if label:
            releases.append(
                {"v": label, "at": created, "note": "Carried over from Dig v1"}
            )

        projects.append(
            {
                "id": pid,
                "name": app["name"],
                "group": APPS_GROUP["id"],
                "type": APP_TYPE["id"],
                "stage": SHIPPED_STAGE if shipped else BUILDING_STAGE,
                "enteredAt": created,
                "when": "done" if shipped else "next",
                "next": "",
                "items": checklist,
                "decisions": [],
                "files": files,
                "links": links,
                "notes": notes,
                "pub": True,
                "wait": None,
                "lastAct": created,
                "releases": releases,
                "people": [],
                "hist": [],
                "quiet": shipped,
                "parked": False,
                "origin": idea_titles.get(app.get("origin_idea_id")),
                "waitHist": [],
            }
        )

    ideas = []
    for row in v1["ideas"]:
        if row.get("promoted_app_id"):
            continue  # v2 removes an idea from Ideas once it is started
        ideas.append(
            {
                "id": f"v1i{row['id']}",
                "text": row["title"],
                "desc": row.get("note") or "",
                "at": _iso(row.get("created_at")),
                "opened": _iso(row["last_opened_at"]) if row.get("last_opened_at") else None,
                "group": "",
            }
        )

    return {
        "org": owner,
        "you": owner.split(" ")[0] if owner != "Your projects" else "",
        "theme": theme,
        "setupDone": True,
        "groups": [dict(APPS_GROUP)],
        "types": [_deep(APP_TYPE)],
        "projects": projects,
        "ideas": ideas,
        "inbox": [],
        "library": [],
        "activity": [],
        "ui": {
            "filterGroup": "all",
            "sort": "activity",
            "ideaSort": "oldest",
            "libFilter": "all",
            "publicOnly": True,
            "ptab": "work",
            "resurfId": None,
            "window": None,
        },
    }


def _deep(value):
    return json.loads(json.dumps(value))


def _rehome(stored_path: str, app_id: int, project_id: str) -> str:
    """Where a v1 attachment ends up once its folder is renamed."""
    old_root = paths.attachments_dir() / str(app_id)
    new_root = paths.project_attachments_dir(project_id)
    path = Path(stored_path)
    try:
        return str(new_root / path.relative_to(old_root))
    except ValueError:
        return stored_path


def move_attachments(v1: dict) -> None:
    """Rename each app's attachment folder to its new project ID."""
    for app in v1["apps"]:
        old = paths.attachments_dir() / str(app["id"])
        new = paths.project_attachments_dir(f"v1a{app['id']}")
        if old.is_dir() and not new.exists():
            new.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old), str(new))


def migrate_if_needed(store: StateStore) -> str:
    """Migrate a v1 file if one is here. Returns what to tell the person."""
    db_path = store.db_path
    if not looks_like_v1(db_path):
        return ""

    backup = paths.v1_backup_path()
    try:
        v1 = read_v1(db_path)
        shutil.copy2(db_path, backup)
        move_attachments(v1)
        state = build_state(v1)
        store.save(json.dumps(state))
    except Exception:
        return (
            "Dig found data from version 1 but could not bring it across. Nothing"
            " was deleted. Your old file is still where it was."
        )

    apps = len(state["projects"])
    ideas = len(state["ideas"])
    return (
        f"Brought {apps} {'app' if apps == 1 else 'apps'} and {ideas}"
        f" {'idea' if ideas == 1 else 'ideas'} over from Dig v1."
        f" The old file is kept as {backup.name}."
    )
