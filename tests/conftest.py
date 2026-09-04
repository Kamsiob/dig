"""Shared fixtures. Every test runs against a throwaway data folder."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dig.storage import StateStore  # noqa: E402


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    root = tmp_path / "dig"
    (root / "history").mkdir(parents=True)
    (root / "attachments").mkdir(parents=True)
    return root


@pytest.fixture()
def store(data_dir: Path) -> StateStore:
    return StateStore(data_dir / "dig.db", data_dir / "history")
