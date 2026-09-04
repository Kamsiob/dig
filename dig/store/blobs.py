"""Files, kept by what they are rather than by what they are called.

Every file Dig is given is hashed and stored once, under its SHA256. Two
records pointing at the same bytes cost one copy. A file record carries the
hash; the name, version, and description live on the record, so renaming a file
or moving it between projects never touches the bytes.

The original file is only ever read. Dig does not modify or move what it is
given.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

CHUNK = 1024 * 1024
LARGE_FILE_BYTES = 250 * 1024 * 1024


@dataclass
class Stored:
    sha256: str
    size: int
    mime: str
    ext: str
    name: str
    deduplicated: bool


def sha256_of(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def guess_mime(path: Path) -> str:
    kind, _ = mimetypes.guess_type(str(path))
    return kind or "application/octet-stream"


def chip(name: str) -> str:
    """The short upper case label a file row shows, for example PDF."""
    suffix = Path(name).suffix.lstrip(".").upper()
    return suffix[:4] if suffix else "FILE"


class BlobStore:
    """The bytes, addressed by their hash."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path_for(self, sha256: str) -> Path:
        """Two levels of fan out, so no directory grows past a few thousand."""
        return self.root / sha256[:2] / sha256[2:4] / sha256

    def has(self, sha256: str) -> bool:
        return self.path_for(sha256).is_file()

    def size_of(self, sha256: str) -> int:
        path = self.path_for(sha256)
        return path.stat().st_size if path.is_file() else 0

    def put(self, source: Path) -> Stored:
        """Take a copy of a file. Identical bytes are only ever stored once."""
        source = Path(source)
        digest, size = sha256_of(source)
        target = self.path_for(digest)
        deduplicated = target.is_file()
        if not deduplicated:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=str(target.parent), prefix=".blob-", suffix=".tmp", delete=False
            ) as handle:
                staged = Path(handle.name)
            try:
                shutil.copyfile(source, staged)
                with open(staged, "rb") as handle:
                    os.fsync(handle.fileno())
                os.replace(str(staged), str(target))
            finally:
                staged.unlink(missing_ok=True)
        return Stored(
            sha256=digest,
            size=size,
            mime=guess_mime(source),
            ext=chip(source.name),
            name=source.name,
            deduplicated=deduplicated,
        )

    def put_bytes(self, data: bytes, name: str) -> Stored:
        """Take a copy of something pasted rather than picked."""
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(data)
            staged = Path(handle.name)
        try:
            stored = self.put(staged)
        finally:
            staged.unlink(missing_ok=True)
        return Stored(
            sha256=stored.sha256,
            size=stored.size,
            mime=guess_mime(Path(name)),
            ext=chip(name),
            name=name,
            deduplicated=stored.deduplicated,
        )

    def read(self, sha256: str) -> bytes:
        return self.path_for(sha256).read_bytes()

    def copy_out(self, sha256: str, target: Path) -> Path:
        """Write the exact original bytes somewhere the person chose."""
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.path_for(sha256), target)
        return target

    def every(self) -> list[str]:
        if not self.root.is_dir():
            return []
        found = []
        for path in self.root.rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                found.append(path.name)
        return found

    def total_size(self) -> int:
        if not self.root.is_dir():
            return 0
        return sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file())

    def unreferenced(self, referenced: set[str]) -> list[str]:
        return [sha for sha in self.every() if sha not in referenced]

    def remove(self, sha256: str) -> int:
        """Delete one blob. Only ever called for a blob nothing points at."""
        path = self.path_for(sha256)
        if not path.is_file():
            return 0
        size = path.stat().st_size
        path.unlink()
        for parent in (path.parent, path.parent.parent):
            try:
                parent.rmdir()
            except OSError:
                break
        return size
