"""Plain records handed between the store and the interface.

These are dumb containers. All behaviour lives in the store.
"""

from __future__ import annotations

from dataclasses import dataclass

FEATURE = "feature"
BUG = "bug"
KINDS = (FEATURE, BUG)


@dataclass(frozen=True)
class Idea:
    """A jotted idea. Title is the first line, note is everything after it."""

    id: int
    title: str
    note: str
    created_at: str
    last_opened_at: str | None
    promoted_app_id: int | None

    @property
    def is_promoted(self) -> bool:
        return self.promoted_app_id is not None

    @property
    def never_opened(self) -> bool:
        return self.last_opened_at is None


@dataclass(frozen=True)
class App:
    """An app in the registry, promoted from an idea or added directly."""

    id: int
    name: str
    description: str
    notes: str
    github_url: str
    version_label: str
    shipped: bool
    origin_idea_id: int | None
    created_at: str

    @property
    def was_dug_from_an_idea(self) -> bool:
        return self.origin_idea_id is not None


@dataclass(frozen=True)
class SheetItem:
    """One line on a feature sheet or a bug sheet. Done or not done. Nothing else."""

    id: int
    app_id: int
    kind: str
    text: str
    done: bool
    created_at: str
    done_at: str | None


@dataclass(frozen=True)
class Attachment:
    """A file copied into the managed store for an app."""

    id: int
    app_id: int
    filename: str
    stored_path: str
    size: int
    is_image: bool
    added_at: str


@dataclass(frozen=True)
class SheetCounts:
    """Live counts for a sheet header: "N open · N done"."""

    open: int
    done: int

    def __str__(self) -> str:
        return f"{self.open} open · {self.done} done"
