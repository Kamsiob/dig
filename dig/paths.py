"""Filesystem locations Dig uses.

Everything lives under the XDG data directory. Nothing is written outside the
user's home, and nothing is ever sent anywhere.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "dig"


def _xdg_data_home() -> Path:
    """The XDG data root, honoring XDG_DATA_HOME when it is set."""
    env = os.environ.get("XDG_DATA_HOME", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".local" / "share"


def data_dir() -> Path:
    """Dig's data folder: ~/.local/share/dig by default."""
    return _xdg_data_home() / APP_DIR_NAME


def db_path() -> Path:
    """The SQLite file holding the whole state document."""
    return data_dir() / "dig.db"


def v1_backup_path() -> Path:
    """Where a migrated Dig v1 database is kept, untouched, forever."""
    return data_dir() / "dig-v1.db.bak"


def history_dir() -> Path:
    """Rolling recovery snapshots, newest twenty kept."""
    return data_dir() / "history"


def attachments_dir() -> Path:
    """Where Dig v1 kept attachments. Only the migration looks here now."""
    return data_dir() / "attachments"


def project_attachments_dir(project_id: str) -> Path:
    """The v1 style attachment folder for one project."""
    return attachments_dir() / str(project_id)


def blobs_dir() -> Path:
    """Every file Dig holds, stored once each, addressed by its SHA256."""
    return data_dir() / "blobs"


def backups_dir() -> Path:
    """Where a full backup lands when no other place is chosen."""
    return data_dir() / "backups"


def ensure_data_dirs() -> Path:
    """Create the data directories on first run. Returns the data folder."""
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    history_dir().mkdir(parents=True, exist_ok=True)
    blobs_dir().mkdir(parents=True, exist_ok=True)
    return root


def package_dir() -> Path:
    """The installed `dig` package directory."""
    return Path(__file__).resolve().parent


def ui_dir() -> Path:
    """The web interface: index.html, app.css, app.js, and the fonts."""
    return package_dir() / "ui"


def project_root() -> Path:
    """The repository or install root that holds `assets/` and `packaging/`."""
    return package_dir().parent
