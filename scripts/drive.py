#!/usr/bin/env python3
"""Drive the real app: run steps in it, read values out, take screenshots.

This is the harness the fidelity pass, the test suite, and the scripted user
pass all run on. It starts Dig exactly as a person would get it, against a data
folder you choose, and walks a plan of steps.

A plan is a JSON list. Each step may carry:

    name   a label, and the screenshot filename when shot is true
    js     JavaScript to run inside the app; its value is recorded
    wait   milliseconds to settle before the screenshot (default 450)
    shot   whether to capture a PNG (default true)

    python scripts/drive.py --data /tmp/run --plan plan.json --out shots
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="XDG_DATA_HOME for this run")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--size", default="1280x840")
    ap.add_argument("--results", default="")
    ap.add_argument("--show", action="store_true", help="use the real display")
    ap.add_argument("--settle", type=int, default=1600, help="ms to wait after load")
    ap.add_argument(
        "--open",
        action="append",
        default=[],
        help="answer the next Open dialog with this path, in order",
    )
    ap.add_argument(
        "--save",
        action="append",
        default=[],
        help="answer the next Save dialog with this path, in order",
    )
    args = ap.parse_args()

    os.environ["XDG_DATA_HOME"] = str(Path(args.data).resolve())
    if not args.show:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-gpu --no-sandbox --in-process-gpu --disable-dev-shm-usage",
    )

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QFileDialog

    from dig import paths
    from dig.bridge import Bridge
    from dig.storage import StateStore
    from dig.window import MainWindow

    # A modal file dialog has nobody to click it, so a run can queue the
    # answers up front. Nothing in the app changes; only the dialog is stubbed.
    if args.open or args.save:
        queued = {"open": list(args.open), "save": list(args.save)}

        def answer(kind):
            def pick(*_a, **_kw):
                chosen = queued[kind].pop(0) if queued[kind] else ""
                return (chosen, "")

            return pick

        QFileDialog.getOpenFileName = staticmethod(answer("open"))
        QFileDialog.getSaveFileName = staticmethod(answer("save"))

    width, height = (int(n) for n in args.size.lower().split("x"))
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication([])
    paths.ensure_data_dirs()
    store = StateStore(paths.db_path(), paths.history_dir())
    result = store.load()

    bridge = Bridge(store)
    window = MainWindow(bridge)
    bridge.attach_window(window)
    bridge.prime(result)
    window.resize(width, height)
    window.load_ui()
    window.show()

    console: list[str] = []
    original = window.page.javaScriptConsoleMessage

    def capture(level, message, line, source):
        console.append(f"{message} ({Path(source).name}:{line})")
        original(level, message, line, source)

    window.page.javaScriptConsoleMessage = capture

    steps = list(plan)
    cursor = {"i": 0}
    results: list[dict] = []

    def finish() -> None:
        payload = {
            "steps": results,
            "console": console,
            "blocked": list(window.interceptor.blocked),
        }
        text = json.dumps(payload, indent=1, default=str)
        if args.results:
            Path(args.results).write_text(text, encoding="utf-8")
        else:
            print(text)
        bridge.flush()
        app.quit()

    def shoot(step: dict, value) -> None:
        entry = {"name": step.get("name", ""), "value": value}
        if step.get("shot", True) and out_dir:
            image = window.grab().toImage()
            target = out_dir / f"{step.get('name', 'step')}.png"
            image.save(str(target))
            entry["shot"] = str(target)
        results.append(entry)
        QTimer.singleShot(80, run_next)

    def run_next() -> None:
        if cursor["i"] >= len(steps):
            finish()
            return
        step = steps[cursor["i"]]
        cursor["i"] += 1
        code = step.get("js") or "null"
        wait = int(step.get("wait", 450))
        window.page.runJavaScript(
            code, lambda value: QTimer.singleShot(wait, lambda: shoot(step, value))
        )

    QTimer.singleShot(args.settle, run_next)
    QTimer.singleShot(args.settle + 240000, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
