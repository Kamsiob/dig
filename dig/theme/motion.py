"""Whether this desktop has asked for less movement.

Qt exposes no reduced-motion hint on Linux, so the desktop's own setting is
read directly. When the answer is yes, Dig drops its highlight fade and any
other movement rather than shortening it.
"""

from __future__ import annotations

import configparser
import os
import subprocess
from pathlib import Path

_answer: bool | None = None


def _from_environment() -> bool | None:
    """An explicit override. Also how the test suite drives this."""
    raw = os.environ.get("DIG_REDUCED_MOTION", "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return None


def _from_kde() -> bool | None:
    """KDE Plasma: an animation speed of zero means no animation."""
    config = Path.home() / ".config" / "kdeglobals"
    if not config.is_file():
        return None
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    try:
        parser.read(config, encoding="utf-8")
        raw = parser.get("KDE", "AnimationDurationFactor", fallback="")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return None
    if not raw.strip():
        return None
    try:
        return float(raw) <= 0.0
    except ValueError:
        return None


def _from_gnome() -> bool | None:
    """GNOME and anything else honouring the org.gnome.desktop.interface key."""
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "enable-animations"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    answer = result.stdout.strip().lower()
    if answer == "false":
        return True
    if answer == "true":
        return False
    return None


def prefers_reduced_motion(refresh: bool = False) -> bool:
    """True when this desktop has asked for reduced motion."""
    global _answer
    if _answer is not None and not refresh:
        return _answer
    for source in (_from_environment, _from_kde, _from_gnome):
        found = source()
        if found is not None:
            _answer = found
            return _answer
    _answer = False
    return _answer
