#!/usr/bin/env python3
"""Cut static font instances from the bundled variable fonts.

Qt loads a variable font at its default axis position and does not vary the
weight afterwards. Fraunces defaults to wght 900 at opsz 9, so every serif in
the app would render Black at the smallest optical size. Pinning the axes here
gives Qt ordinary weighted families it can style normally.

Run from the repo root after changing a source font:

    .venv/bin/python scripts/build_fonts.py

fonttools is a build-time tool only; Dig does not need it to run.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

FONTS = Path(__file__).resolve().parent.parent / "fonts"

# Fraunces is the display serif: titles, headings, the wordmark, the jot field.
# opsz 24 suits the 16-40px range it is used at. SOFT and WONK stay at the
# font's own defaults, which is what the reference mockup renders.
FRAUNCES_SOURCE = "Fraunces[SOFT,WONK,opsz,wght].ttf"
# opsz, SOFT and WONK are pinned first and quietly: the font's STAT table has
# no named value for opsz 24, so only the weight cut can carry a style name.
FRAUNCES_PREPIN = {"opsz": 24, "SOFT": 0, "WONK": 1}
FRAUNCES_CUTS = {
    "Fraunces-Regular.ttf": {"wght": 400},
    "Fraunces-SemiBold.ttf": {"wght": 600},
    "Fraunces-Bold.ttf": {"wght": 700},
}

# IBM Plex Sans is the interface face: body, buttons, navigation.
PLEX_SANS_SOURCE = "IBMPlexSans[wdth,wght].ttf"
PLEX_SANS_CUTS = {
    "IBMPlexSans-Regular.ttf": {"wght": 400, "wdth": 100},
    "IBMPlexSans-Medium.ttf": {"wght": 500, "wdth": 100},
    "IBMPlexSans-SemiBold.ttf": {"wght": 600, "wdth": 100},
}


def cut(
    source_name: str,
    targets: dict[str, dict[str, float]],
    prepin: dict[str, float] | None = None,
) -> None:
    source = FONTS / source_name
    if not source.is_file():
        raise SystemExit(f"Missing source font: {source}")
    for filename, axes in targets.items():
        font = TTFont(source)
        if prepin:
            font = instancer.instantiateVariableFont(
                font, prepin, updateFontNames=False
            )
        static = instancer.instantiateVariableFont(font, axes, updateFontNames=True)
        out = FONTS / filename
        static.save(out)
        print(f"  {filename:30} {dict(prepin or {}, **axes)}")


def main() -> int:
    print("Cutting static instances into fonts/")
    cut(FRAUNCES_SOURCE, FRAUNCES_CUTS, FRAUNCES_PREPIN)
    cut(PLEX_SANS_SOURCE, PLEX_SANS_CUTS)
    print("Done. IBM Plex Mono already ships as static Regular and Medium.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
