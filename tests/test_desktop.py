"""Putting Dig in the applications menu, and taking it out again."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dig import desktop


@pytest.fixture()
def home(tmp_path: Path, monkeypatch):
    """A home folder with nothing in it, and no menu entry anywhere."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.delenv("APPIMAGE", raising=False)
    return tmp_path


def test_a_path_with_a_space_in_it_is_quoted() -> None:
    """A desktop entry's Exec is split on spaces. Unquoted, a launcher runs the
    first word and hands it the rest as arguments, and nothing opens."""
    import shlex

    spaced = Path("/var/home/someone/Their Apps/Dig/run")
    line = desktop.quote(spaced)
    assert shlex.split(line) == [str(spaced)], "the launcher would run the wrong thing"

    plain = Path("/home/someone/Applications/Dig.AppImage")
    assert desktop.quote(plain) == str(plain), "a path with no space needs no quotes"
    assert shlex.split(desktop.quote(plain)) == [str(plain)]


def test_install_writes_a_launcher_that_points_at_the_appimage(home, monkeypatch) -> None:
    appimage = home / "Applications" / "Dig-2.0.0-x86_64.AppImage"
    appimage.parent.mkdir(parents=True)
    appimage.write_bytes(b"not really an appimage")
    monkeypatch.setenv("APPIMAGE", str(appimage))

    assert desktop.install() == 0

    entry = desktop.launcher_path().read_text()
    assert f"Exec={appimage}" in entry
    assert "Icon=dig" in entry
    assert "StartupWMClass=dig" in entry
    assert desktop.command_path().resolve() == appimage.resolve()


def test_install_quotes_the_path_when_it_has_to(home, monkeypatch) -> None:
    appimage = home / "My Apps" / "Dig.AppImage"
    appimage.parent.mkdir(parents=True)
    appimage.write_bytes(b"x")
    monkeypatch.setenv("APPIMAGE", str(appimage))

    desktop.install()

    line = [
        l for l in desktop.launcher_path().read_text().splitlines()
        if l.startswith("Exec=")
    ][0]
    import shlex

    assert shlex.split(line[len("Exec="):]) == [str(appimage)]


def test_install_brings_the_icons(home) -> None:
    desktop.install()
    icons = desktop.icons_root()
    assert (icons / "256x256/apps/dig.png").exists()
    assert (icons / "scalable/apps/dig.svg").exists()


def test_the_entry_puts_dig_in_one_place_in_the_menu(home) -> None:
    desktop.install()
    line = [
        l for l in desktop.launcher_path().read_text().splitlines()
        if l.startswith("Categories=")
    ][0]
    mains = {"AudioVideo", "Audio", "Video", "Development", "Education", "Game",
             "Graphics", "Network", "Office", "Science", "Settings", "System",
             "Utility"}
    given = {c for c in line[len("Categories="):].split(";") if c}
    assert len(given & mains) == 1, f"{given & mains} would list Dig more than once"


def test_uninstall_removes_what_install_wrote_and_leaves_the_data(home) -> None:
    data = Path(os.environ["XDG_DATA_HOME"]) / "dig"
    data.mkdir(parents=True)
    (data / "dig.db").write_bytes(b"someone's work")

    desktop.install()
    assert desktop.launcher_path().exists()

    assert desktop.uninstall() == 0
    assert not desktop.launcher_path().exists()
    assert not desktop.command_path().exists()
    assert not (desktop.icons_root() / "256x256/apps/dig.png").exists()
    assert (data / "dig.db").read_bytes() == b"someone's work"


def test_uninstall_on_a_machine_it_was_never_installed_on_is_quiet(home) -> None:
    assert desktop.uninstall() == 0


def test_a_checkout_points_at_its_run_script(home, monkeypatch) -> None:
    monkeypatch.delenv("APPIMAGE", raising=False)
    desktop.install()
    entry = desktop.launcher_path().read_text()
    assert entry.rstrip().endswith("StartupWMClass=dig")
    assert "/run" in entry or "python" in entry
