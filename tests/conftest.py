"""Shared fixtures. Every test runs against a throwaway data folder."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# These have to be in place before Qt starts, so they are set at import time.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--disable-gpu --no-sandbox --in-process-gpu --disable-dev-shm-usage",
)
os.environ.setdefault("DIG_REDUCE_MOTION", "0")

from dig.store import Store  # noqa: E402


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    root = tmp_path / "dig"
    (root / "history").mkdir(parents=True)
    (root / "attachments").mkdir(parents=True)
    return root


@pytest.fixture()
def store(data_dir: Path) -> Store:
    return Store(data_dir / "dig.db", data_dir / "history")


@pytest.fixture(scope="session")
def qt_app():
    from tests.uiharness import app

    return app()


@pytest.fixture()
def home(tmp_path: Path, monkeypatch) -> Path:
    """A fresh machine: an empty data folder Dig has never seen."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def launch(qt_app, home: Path):
    """Start Dig once the test has arranged the data folder it should find."""
    from tests.uiharness import UI

    started: list = []

    def go(size: tuple[int, int] = (1280, 840)):
        running = UI(size=size)
        started.append(running)
        return running.start()

    yield go
    for running in started:
        running.close()


@pytest.fixture()
def ui(launch):
    """A running copy of Dig on a fresh machine."""
    return launch()
