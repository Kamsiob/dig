"""Palettes, fonts, and the stylesheet that binds them."""

from dig.theme.fonts import mono, register_fonts, sans, serif
from dig.theme.motion import prefers_reduced_motion
from dig.theme.theme import (
    APPEARANCE_KEY,
    DARK_MODE,
    LIGHT_MODE,
    MODE_LABELS,
    MODES,
    SYSTEM_MODE,
    ThemeManager,
)
from dig.theme.tokens import DARK, LIGHT, Palette, palette_for

__all__ = [
    "APPEARANCE_KEY",
    "DARK",
    "DARK_MODE",
    "LIGHT",
    "LIGHT_MODE",
    "MODES",
    "MODE_LABELS",
    "Palette",
    "SYSTEM_MODE",
    "ThemeManager",
    "mono",
    "palette_for",
    "prefers_reduced_motion",
    "register_fonts",
    "sans",
    "serif",
]
