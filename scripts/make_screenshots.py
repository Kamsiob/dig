#!/usr/bin/env python3
"""Take the README screenshots from the running app.

These are captures of the real window with real data, not mockups. The data
lives in a throwaway profile, so running this never touches your own ideas.

    .venv/bin/python scripts/make_screenshots.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SHOTS = ROOT / "docs" / "screenshots"

# Ages in days, so the ledger and the unearthed block read like a real week.
IDEAS = [
    ("Pocket wiki for the channel",
     "One markdown file per video: gear used, commands run, links mentioned. "
     "Searchable. Becomes the description generator later.", 46),
    ("Bulk image renamer with EXIF", "rename by capture date and camera body", 31),
    ("Local podcast transcriber",
     "whisper.cpp on the mini PC, drop a file in a folder", 20),
    ("Thumbnail A/B logger",
     "track which thumbnail style correlates with CTR over time", 9),
    ("RSS-to-Telegram digest",
     "daily channel post built from selected feeds, runs on the mini PC", 5),
    ("Clipboard history that expires",
     "everything auto-deletes after 24h, zero persistence by design", 2),
]


def seed(store, workspace: Path):
    """Build a believable registry to photograph."""
    from PySide6.QtGui import QImage

    from dig.storage import BUG, FEATURE

    now = datetime.now(timezone.utc)
    for title, note, days in IDEAS:
        idea = store.create_idea(f"{title}\n{note}")
        store.conn.execute(
            "UPDATE ideas SET created_at = ? WHERE id = ?",
            ((now - timedelta(days=days)).isoformat(timespec="seconds"), idea.id),
        )

    origin = store.create_idea(
        "One place to start/stop all the local AI stuff\n"
        "service control, models, and logs in one window"
    )
    store.conn.execute(
        "UPDATE ideas SET created_at = ? WHERE id = ?",
        ((now - timedelta(days=160)).isoformat(timespec="seconds"), origin.id),
    )
    hub = store.promote_idea(
        origin.id,
        "Local AI Hub",
        "Desktop control panel for Ollama, Open WebUI, and ComfyUI. Service "
        "control, model management, install-by-URL with hash verification, and "
        "a provenance manifest system.",
        github_url="https://github.com/kamsiob/local-ai-hub",
        version_label="v1.2.0",
        shipped=True,
    )
    store.update_app(
        hub.id,
        notes=(
            "Lead with the hash-verification story: nobody else does provenance "
            "locally.\n\n"
            "Demo order: service control, then model install, then crash "
            "surfacing.\n\n"
            "Mention the Bazzite immutable-/usr workaround; it is the video hook."
        ),
    )

    for text in (
        "Model install by URL with hash check",
        "Crash surfacing for all three services",
        "Provenance manifest via Civitai and HF",
    ):
        item = store.add_sheet_item(hub.id, FEATURE, text)
        store.toggle_sheet_item(item.id)
    for text in ("Disk usage per model, sortable", "One-click log bundle for reports"):
        store.add_sheet_item(hub.id, FEATURE, text)

    for text in ("Window grouping wrong on Wayland", "GGUF warning fires twice"):
        item = store.add_sheet_item(hub.id, BUG, text)
        store.toggle_sheet_item(item.id)
    store.add_sheet_item(hub.id, BUG, "Status lamp stale after Ollama restart")

    sources = workspace / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    for name, colour in (
        ("home.png", 0x2E4034),
        ("models.png", 0xA5572E),
        ("install-flow.png", 0xC0954C),
    ):
        path = sources / name
        image = QImage(300, 190, QImage.Format.Format_RGB32)
        image.fill(colour)
        image.save(str(path))
        store.attach_file(hub.id, path)

    notes = sources / "release-notes-draft.md"
    notes.write_text("# Release notes\n\nDraft.\n")
    store.attach_file(hub.id, notes)

    bearings = store.create_app(
        "Bearings",
        "A living field guide for people switching to Bazzite Linux. "
        "Local-only, no telemetry.",
        github_url="https://github.com/kamsiob/bearings",
        version_label="v0.9.0",
        shipped=True,
    )
    store.add_sheet_item(bearings.id, FEATURE, "Offline search across every card")
    store.add_sheet_item(bearings.id, BUG, "Card anchors drift on resize")

    logbook = store.create_app(
        "Logbook",
        "An episode planning ledger for solo video creators. "
        "Local-first, no account.",
        github_url="https://github.com/kamsiob/logbook",
        version_label="v1.0.0",
        shipped=True,
    )
    store.add_sheet_item(logbook.id, FEATURE, "Export a shot list as plain text")

    return hub


def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="dig-screenshots-"))
    # A throwaway profile: photographing the app must never touch real data.
    os.environ["XDG_DATA_HOME"] = str(workspace / "data")

    from dig.app import build_application
    from dig.storage import Store
    from dig.theme import ThemeManager
    from dig.ui.capture import CaptureDialog
    from dig.ui.window import MainWindow

    SHOTS.mkdir(parents=True, exist_ok=True)
    app = build_application([])

    store = Store(
        db_file=workspace / "data" / "dig" / "dig.db",
        attachments_root=workspace / "data" / "dig" / "attachments",
    ).open()
    hub = seed(store, workspace)

    def settle(times: int = 8) -> None:
        for _ in range(times):
            app.processEvents()

    taken: list[str] = []

    for mode in ("light", "dark"):
        theme = ThemeManager(mode)
        theme.apply()
        window = MainWindow(store, theme)
        window.resize(1180, 820)
        window.show()
        settle()

        window.go_to("home")
        settle()
        target = SHOTS / f"home-{mode}.png"
        window.grab().save(str(target))
        taken.append(target.name)

        if mode == "light":
            window.open_app(hub.id)
            settle()
            target = SHOTS / "app-detail.png"
            window.grab().save(str(target))
            taken.append(target.name)

            window.go_to("home")
            settle()
            dialog = CaptureDialog(store, theme.palette, hub.id, window)
            dialog.show()
            dialog.text_field.setText("Disk usage per model, sortable")
            settle()

            # The dialog is its own top-level window, so grabbing the main
            # window alone would photograph the screen behind it. The two are
            # composited the way they actually appear, scrim and all.
            from PySide6.QtGui import QPainter

            base = window.grab()
            painter = QPainter(base)
            painter.drawPixmap(0, 0, dialog.grab())
            painter.end()

            target = SHOTS / "capture.png"
            base.save(str(target))
            taken.append(target.name)
            dialog.close()
            settle()

        window.close()
        settle()

    store.close()
    for name in taken:
        print(f"  docs/screenshots/{name}")
    print(f"\nProfile used and discarded: {workspace}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
