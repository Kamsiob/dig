"""Shared test fixtures. Every test runs against a throwaway data folder."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dig.storage import Store  # noqa: E402


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """An empty stand-in for ~/.local/share/dig."""
    return tmp_path / "dig-data"


@pytest.fixture
def store(data_dir: Path):
    """An open store on a fresh database."""
    s = Store(db_file=data_dir / "dig.db", attachments_root=data_dir / "attachments")
    s.open()
    yield s
    s.close()


@pytest.fixture
def sample_file(tmp_path: Path):
    """Builds a real file on disk to attach."""

    def _make(name: str, content: bytes = b"dig test payload") -> Path:
        folder = tmp_path / "sources"
        folder.mkdir(exist_ok=True)
        path = folder / name
        path.write_bytes(content)
        return path

    return _make
