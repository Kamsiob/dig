"""Putting Dig in the applications menu, and taking it out again.

An AppImage is one file with nothing beside it, so the way it gets a menu entry
and an icon is to write them itself. `dig --install` does that from wherever the
AppImage happens to be sitting; `dig --uninstall` removes what it wrote and
never touches your data.

The same two commands work from a checkout, where they point at `run` instead.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from dig import __app_name__, __version__

SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

ENTRY = """[Desktop Entry]
Type=Application
Version=1.0
Name={name}
GenericName=Project Tracker
Comment=Every project you are working on, in one place
Exec={exec_line}
Icon=dig
Terminal=false
Categories=Office;ProjectManagement;
Keywords=projects;stages;ideas;roadmap;decisions;
StartupNotify=true
StartupWMClass=dig
"""


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")


def launcher_path() -> Path:
    return data_home() / "applications" / "dig.desktop"


def icons_root() -> Path:
    return data_home() / "icons" / "hicolor"


def command_path() -> Path:
    return Path.home() / ".local/bin" / "dig"


def quote(path: Path) -> str:
    """A path a desktop entry's Exec can hold.

    Exec is split on spaces, and a folder with a space in its name is
    ordinary. Unquoted, a launcher runs the first word and hands it the rest
    as arguments, and nothing opens at all.
    """
    text = str(path)
    if '"' in text:
        text = text.replace('"', '\\"')
    return f'"{text}"' if " " in text or '"' in str(path) else text


def running_from() -> Path:
    """The thing a person would run to start Dig again.

    Inside an AppImage that is the AppImage itself, which the runtime puts in
    APPIMAGE. From a checkout it is the `run` script beside the package.
    """
    appimage = os.environ.get("APPIMAGE")
    if appimage and Path(appimage).exists():
        return Path(appimage).resolve()
    here = Path(__file__).resolve().parent.parent
    run = here / "run"
    if run.exists():
        return run
    return Path(sys.executable).resolve()


def icon_sources() -> dict:
    """The icon files, wherever this copy of Dig keeps them."""
    root = Path(__file__).resolve().parent.parent / "assets" / "icons"
    found = {}
    for size in SIZES:
        one = root / f"dig-{size}.png"
        if one.exists():
            found[size] = one
    svg = root / "dig.svg"
    if svg.exists():
        found["scalable"] = svg
    return found


def _refresh() -> None:
    for command in (
        ["update-desktop-database", "-q", str(launcher_path().parent)],
        ["gtk-update-icon-cache", "-q", "-t", "-f", str(icons_root())],
    ):
        if shutil.which(command[0]):
            try:
                subprocess.run(command, check=False, capture_output=True, timeout=20)
            except Exception:
                pass


def install() -> int:
    """Write the menu entry, the icons, and the `dig` command."""
    target = running_from()
    launcher = launcher_path()
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(ENTRY.format(name=__app_name__, exec_line=quote(target)))
    launcher.chmod(0o755)

    icons = icon_sources()
    for size, source in icons.items():
        where = icons_root() / (
            "scalable/apps" if size == "scalable" else f"{size}x{size}/apps"
        )
        where.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, where / ("dig.svg" if size == "scalable" else "dig.png"))

    command = command_path()
    command.parent.mkdir(parents=True, exist_ok=True)
    if command.exists() or command.is_symlink():
        command.unlink()
    command.symlink_to(target)

    _refresh()

    print(f"{__app_name__} {__version__} is in your applications menu.")
    print(f"  Runs:      {target}")
    print(f"  Launcher:  {launcher}")
    print(f"  Command:   {command}")
    if not icons:
        print("  No icons were found beside this copy, so the menu entry has none.")
    if str(command.parent) not in os.environ.get("PATH", "").split(":"):
        print(f"\n  {command.parent} is not on your PATH, so `dig` will not be found.")
        print("  Add it to your shell profile, or run the AppImage directly.")
    return 0


def uninstall() -> int:
    """Remove what install wrote. Your data is never touched."""
    launcher_path().unlink(missing_ok=True)
    for size in SIZES:
        (icons_root() / f"{size}x{size}/apps/dig.png").unlink(missing_ok=True)
    (icons_root() / "scalable/apps/dig.svg").unlink(missing_ok=True)
    command = command_path()
    if command.is_symlink() or command.exists():
        command.unlink()
    _refresh()
    print(f"{__app_name__} is out of your applications menu.")
    print(f"  Your data is still at {data_home() / 'dig'}.")
    print("  Delete that folder yourself if you want it gone.")
    return 0
