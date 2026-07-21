"""The two palettes.

Values come from DESIGN.md and design/dig-design.html. Nothing in the interface
hard-codes a colour: everything reads a token from here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """One complete look. Both palettes carry exactly the same tokens."""

    name: str
    is_dark: bool

    bg: str
    surface: str
    surface_deep: str
    surface_raised: str
    seam: str

    ink: str
    ink_dim: str
    ink_faint: str

    accent: str
    accent_hover: str
    accent_glow: str
    on_accent: str

    copper: str
    verdigris: str

    map_ink: str
    map_accent: str
    shadow: str

    # The strata gauge on the Unearthed block: four stacked soil bands,
    # the deepest of which is always copper.
    strata: tuple[str, str, str, str]

    # Scrim behind a modal dialog.
    scrim: str


LIGHT = Palette(
    name="Field Notes",
    is_dark=False,
    bg="#EFE8D8",
    surface="#F5EFE1",
    surface_deep="#EBE3CF",
    surface_raised="#FAF6EB",
    seam="#D9CFB6",
    ink="#33372A",
    ink_dim="#6C6D59",
    ink_faint="#9B9781",
    accent="#A97A16",
    accent_hover="#8F6708",
    accent_glow="rgba(169, 122, 22, 0.16)",
    on_accent="#FFFDF4",
    copper="#A5572E",
    verdigris="#4E7A62",
    map_ink="rgba(64, 66, 48, 0.16)",
    map_accent="rgba(169, 122, 22, 0.28)",
    shadow="rgba(80, 70, 40, 0.16)",
    strata=("#CDC3A4", "#B3A57E", "#C0954C", "#A5572E"),
    scrim="rgba(235, 227, 207, 0.72)",
)

DARK = Palette(
    name="Excavation at Dusk",
    is_dark=True,
    bg="#0B0F0B",
    surface="#16201A",
    surface_deep="#10160F",
    surface_raised="#1E2C22",
    seam="#2E3F32",
    ink="#EFE6D4",
    ink_dim="#A9A493",
    ink_faint="#6F6F60",
    accent="#D9A13B",
    accent_hover="#EDB44E",
    accent_glow="rgba(217, 161, 59, 0.15)",
    on_accent="#1A1305",
    copper="#C46A3F",
    verdigris="#6FA08A",
    map_ink="rgba(239, 230, 212, 0.10)",
    map_accent="rgba(217, 161, 59, 0.22)",
    shadow="rgba(0, 0, 0, 0.5)",
    strata=("#2A3A2C", "#40492E", "#6E5A2E", "#C46A3F"),
    scrim="rgba(11, 15, 11, 0.72)",
)


def palette_for(is_dark: bool) -> Palette:
    return DARK if is_dark else LIGHT
