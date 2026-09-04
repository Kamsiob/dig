"""Drive the real interface from a test.

Starts the actual window, against a data folder the test owns, and runs
JavaScript in it synchronously so a test can read the app's own state back.
This is the same app a person launches; nothing here is a stand in for it.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog

from dig import paths
from dig.bridge import Bridge
from dig.store import Store
from dig.window import MainWindow

READY_TIMEOUT_MS = 20000


def pump(ms: int) -> None:
    """Let Qt get on with things for a moment."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


class UI:
    """One running copy of Dig."""

    def __init__(self, size: tuple[int, int] = (1280, 840)) -> None:
        self.size = size
        self.window: MainWindow | None = None
        self.bridge: Bridge | None = None
        self.store: Store | None = None
        self.console: list[str] = []
        self.opens: list[str] = []
        self.saves: list[str] = []
        self._patch_dialogs()

    # ------------------------------------------------------------- lifecycle

    def start(self) -> "UI":
        paths.ensure_data_dirs()
        self.store = Store(paths.db_path(), paths.history_dir())

        from dig.startup import open_state

        result = open_state(self.store)

        self.bridge = Bridge(self.store)
        self.window = MainWindow(self.bridge)
        self.bridge.attach_window(self.window)
        self.bridge.prime(result)
        self.window.resize(*self.size)
        self.window.load_ui()
        self.window.show()

        original = self.window.page.javaScriptConsoleMessage

        def capture(level, message, line, source):
            self.console.append(f"{message} ({Path(source).name}:{line})")
            original(level, message, line, source)

        self.window.page.javaScriptConsoleMessage = capture
        self._await_ready()
        return self

    def _await_ready(self) -> None:
        waited = 0
        while waited < READY_TIMEOUT_MS:
            pump(120)
            waited += 120
            if self.raw("typeof READY!=='undefined'&&READY&&!!S"):
                pump(120)
                return
        raise AssertionError("the interface never finished loading")

    def restart(self) -> "UI":
        """Close and open again, the way a person would."""
        self.close()
        pump(250)
        return self.start()

    def close(self) -> None:
        """Close the way a person does, and wait for the window to actually go."""
        if self.window is None:
            return
        window = self.window
        window.close()
        for _ in range(30):
            pump(30)
            if not window.isVisible():
                break
        self.bridge.flush()
        self.window = None
        window.deleteLater()
        pump(150)

    # ------------------------------------------------------------ javascript

    def raw(self, code: str):
        """Run JavaScript and wait for its value."""
        holder = {}
        loop = QEventLoop()

        def done(value):
            holder["value"] = value
            loop.quit()

        QTimer.singleShot(READY_TIMEOUT_MS, loop.quit)
        self.window.page.runJavaScript(code, done)
        loop.exec()
        return holder.get("value")

    def js(self, expression: str):
        """Run an expression and get its value back through JSON."""
        value = self.raw(f"JSON.stringify((function(){{return ({expression})}})())")
        if value in (None, ""):
            return None
        return json.loads(value)

    def run(self, statements: str, settle: int = 260):
        """Run statements, then let animations and the debounced save settle."""
        self.raw(f"(function(){{{statements}}})();1")
        pump(settle)

    def state(self) -> dict:
        return self.js("persist()")

    def on_disk(self) -> dict | None:
        """What actually reached the database."""
        self.raw("window.flushSave&&window.flushSave();1")
        pump(120)
        self.bridge.flush()
        return self.store.load().state

    def text(self, selector: str) -> str:
        return self.js(
            f"(document.querySelector({json.dumps(selector)})||{{}}).textContent||''"
        )

    def html(self, selector: str = ".main") -> str:
        return self.js(
            f"(document.querySelector({json.dumps(selector)})||{{}}).innerHTML||''"
        )

    def count(self, selector: str) -> int:
        return self.js(f"document.querySelectorAll({json.dumps(selector)}).length")

    def click(self, selector: str, settle: int = 300) -> None:
        found = self.js(
            f"(function(){{var e=document.querySelector({json.dumps(selector)});"
            f"if(!e)return false;e.click();return true}})()"
        )
        assert found, f"nothing to click: {selector}"
        pump(settle)

    def toasts(self) -> list[str]:
        return self.js("S.toasts.map(function(t){return t.msg})") or []

    def key(self, key: str, ctrl: bool = False, settle: int = 300) -> None:
        self.raw(
            "document.dispatchEvent(new KeyboardEvent('keydown',{key:"
            f"{json.dumps(key)},ctrlKey:{'true' if ctrl else 'false'},bubbles:true}}));1"
        )
        pump(settle)

    # ---------------------------------------------------------- file dialogs

    def queue_open(self, *paths_: str) -> None:
        self.opens.extend(str(p) for p in paths_)

    def queue_save(self, *paths_: str) -> None:
        self.saves.extend(str(p) for p in paths_)

    def _patch_dialogs(self) -> None:
        harness = self

        def open_dialog(*_a, **_kw):
            return (harness.opens.pop(0) if harness.opens else "", "")

        def save_dialog(*_a, **_kw):
            return (harness.saves.pop(0) if harness.saves else "", "")

        QFileDialog.getOpenFileName = staticmethod(open_dialog)
        QFileDialog.getSaveFileName = staticmethod(save_dialog)


def app() -> QApplication:
    existing = QApplication.instance()
    return existing or QApplication([])
