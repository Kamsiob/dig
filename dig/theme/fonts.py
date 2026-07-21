"""Register the bundled fonts.

Dig never uses an OS default font for visible text. If a bundled file cannot be
loaded the interface still runs, but the fallback is recorded so it can be seen
rather than silently accepted.
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase

from dig import paths

# Static instances, cut from the variable sources by scripts/build_fonts.py.
# The variable files are not loaded directly: Qt would take each at its default
# axis position and never vary it, which for Fraunces means Black at opsz 9.
SERIF_FILES = (
    "Fraunces-Regular.ttf",
    "Fraunces-SemiBold.ttf",
    "Fraunces-Bold.ttf",
)
SANS_FILES = (
    "IBMPlexSans-Regular.ttf",
    "IBMPlexSans-Medium.ttf",
    "IBMPlexSans-SemiBold.ttf",
)
MONO_FILES = ("IBMPlexMono-Regular.ttf", "IBMPlexMono-Medium.ttf")

# Filled in by register_fonts(). Read through the helpers below.
_families: dict[str, str] = {}
_missing: list[str] = []


def _load(filenames: tuple[str, ...]) -> str:
    """Load font files and return the family name the first one registered as."""
    family = ""
    for filename in filenames:
        path = paths.fonts_dir() / filename
        if not path.is_file():
            _missing.append(filename)
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            _missing.append(filename)
            continue
        registered = QFontDatabase.applicationFontFamilies(font_id)
        if registered and not family:
            family = registered[0]
    return family


def register_fonts() -> dict[str, str]:
    """Load every bundled family. Safe to call more than once."""
    if _families:
        return _families
    _families["serif"] = _load(SERIF_FILES) or "Georgia"
    _families["sans"] = _load(SANS_FILES) or "DejaVu Sans"
    _families["mono"] = _load(MONO_FILES) or "DejaVu Sans Mono"
    return _families


def missing_font_files() -> list[str]:
    """Bundled files that failed to load. Empty when everything is in place."""
    return list(_missing)


def serif() -> str:
    """Fraunces: idea titles, app names, headings, the wordmark, the jot field."""
    return register_fonts()["serif"]


def sans() -> str:
    """IBM Plex Sans: body text, buttons, navigation, descriptions."""
    return register_fonts()["sans"]


def mono() -> str:
    """IBM Plex Mono: metadata, timestamps, eyebrows, counts, chips, key hints."""
    return register_fonts()["mono"]


def font(
    family: str,
    size: float,
    weight: QFont.Weight = QFont.Weight.Normal,
    letter_spacing: float = 0.0,
) -> QFont:
    """Build a QFont, applying letter spacing as a percentage when asked."""
    f = QFont(family)
    f.setPointSizeF(size)
    f.setWeight(weight)
    if letter_spacing:
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 100 + letter_spacing)
    return f
