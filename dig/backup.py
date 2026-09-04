"""Backing everything up, and putting it back.

A JSON export is not a backup, because it does not carry the files. A backup is
one zip holding the whole document, every blob, and a manifest saying which
version of Dig wrote it and when.

Restoring always takes a backup of what is there first, without being asked.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dig import __version__
from dig.store.schema import SCHEMA_VERSION

MANIFEST = "dig-backup.json"
DOCUMENT = "state.json"
BLOB_DIR = "blobs/"
KEEP_SCHEDULED = 10


@dataclass
class Backup:
    path: Path
    made_at: str
    version: str
    schema: int
    projects: int
    ideas: int
    blobs: int
    size: int


def referenced_blobs(state: dict) -> set[str]:
    """Every hash the document points at."""
    found: set[str] = set()

    def take(files) -> None:
        for item in files or []:
            if isinstance(item, dict) and item.get("sha256"):
                found.add(item["sha256"])

    for project in state.get("projects") or []:
        take(project.get("files"))
    for group in state.get("groups") or []:
        take(group.get("files"))
    take(state.get("libraryFiles"))
    return found


def write_backup(target: Path, state: dict, blobs) -> Backup:
    """One zip: the document, every blob it points at, and a manifest."""
    target = Path(target)
    if target.suffix.lower() != ".zip":
        target = target.with_suffix(".zip")
    target.parent.mkdir(parents=True, exist_ok=True)

    hashes = referenced_blobs(state)
    made_at = datetime.now().isoformat(timespec="seconds")
    manifest = {
        "dig": __version__,
        "schema": SCHEMA_VERSION,
        "made_at": made_at,
        "projects": len(state.get("projects") or []),
        "ideas": len(state.get("ideas") or []),
        "blobs": len(hashes),
    }

    staging = target.with_name(target.name + ".part")
    try:
        with zipfile.ZipFile(staging, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST, json.dumps(manifest, indent=2))
            archive.writestr(DOCUMENT, json.dumps(state, default=str))
            for sha in sorted(hashes):
                if blobs.has(sha):
                    archive.writestr(BLOB_DIR + sha, blobs.read(sha))
        staging.replace(target)
    finally:
        if staging.exists():
            staging.unlink(missing_ok=True)

    return Backup(
        path=target, made_at=made_at, version=__version__, schema=SCHEMA_VERSION,
        projects=manifest["projects"], ideas=manifest["ideas"],
        blobs=manifest["blobs"], size=target.stat().st_size,
    )


def read_manifest(source: Path) -> dict | None:
    """What a backup says it holds, or nothing if it is not one of Dig's."""
    try:
        with zipfile.ZipFile(source) as archive:
            names = set(archive.namelist())
            if MANIFEST not in names or DOCUMENT not in names:
                return None
            manifest = json.loads(archive.read(MANIFEST).decode("utf-8"))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None
    if not isinstance(manifest, dict) or "made_at" not in manifest:
        return None
    manifest["blobs_present"] = sum(1 for n in names if n.startswith(BLOB_DIR))
    return manifest


def read_backup(source: Path) -> tuple[dict, list[tuple[str, bytes]]]:
    """The document and the blobs inside a backup."""
    with zipfile.ZipFile(source) as archive:
        state = json.loads(archive.read(DOCUMENT).decode("utf-8"))
        blobs = [
            (name[len(BLOB_DIR):], archive.read(name))
            for name in archive.namelist()
            if name.startswith(BLOB_DIR) and len(name) > len(BLOB_DIR)
        ]
    return state, blobs


def scheduled_is_due(folder: Path, cadence: str) -> bool:
    """Whether a quiet backup is owed, given how recently one was made."""
    if cadence not in ("daily", "weekly"):
        return False
    folder = Path(folder)
    if not folder.is_dir():
        return True
    made = sorted(folder.glob("dig-backup-*.zip"))
    if not made:
        return True
    newest = max(p.stat().st_mtime for p in made)
    span = 86400 if cadence == "daily" else 7 * 86400
    return (datetime.now().timestamp() - newest) >= span


def trim_scheduled(folder: Path, keep: int = KEEP_SCHEDULED) -> int:
    made = sorted(Path(folder).glob("dig-backup-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for old in made[keep:]:
        old.unlink(missing_ok=True)
        removed += 1
    return removed


def scheduled_name() -> str:
    return f"dig-backup-{datetime.now():%Y%m%d-%H%M%S}.zip"
