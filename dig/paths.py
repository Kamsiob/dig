"""Filesystem locations Dig uses.

Everything lives under the XDG data directory. Nothing is written outside the
user's home, and nothing is ever sent anywhere.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "dig"


def _xdg_data_home() -> Path:
    """The XDG data root, honouring XDG_DATA_HOME when it is set."""
    env = os.environ.get("XDG_DATA_HOME", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".local" / "share"


def data_dir() -> Path:
    """Dig's data folder: ~/.local/share/dig by default."""
    return _xdg_data_home() / APP_DIR_NAME


def db_path() -> Path:
    """The SQLite database file."""
    return data_dir() / "dig.db"


def attachments_dir() -> Path:
    """Root of the managed attachment store."""
    return data_dir() / "attachments"


def app_attachments_dir(app_id: int) -> Path:
    """The managed attachment folder for one app."""
    return attachments_dir() / str(app_id)


def ensure_data_dirs() -> Path:
    """Create the data directories on first run. Returns the data folder."""
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    attachments_dir().mkdir(parents=True, exist_ok=True)
    return root


def package_dir() -> Path:
    """The installed `dig` package directory."""
    return Path(__file__).resolve().parent


def project_root() -> Path:
    """The repository / install root that holds `fonts/` and `assets/`."""
    return package_dir().parent


def fonts_dir() -> Path:
    """Bundled OFL font files."""
    return project_root() / "fonts"
