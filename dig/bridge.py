"""The bridge between the web interface and this computer.

Everything the interface cannot do on its own goes through here: reading and
writing the state document, copying files into the managed attachments folder,
exporting and importing, rendering PDFs, opening links and folders, and
reporting the desktop's color scheme and reduce-motion setting.

Nothing in this file opens a socket. Dig makes no network calls.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QMarginsF,
    QObject,
    QStandardPaths,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QFileDialog

from dig import __app_name__, __version__, paths
from dig.storage import LoadResult, StateStore

SAVE_DEBOUNCE_MS = 300

# A bare address like github.com/kamsiob/dig is a link. A phrase like
# "Google Play" is a label the person typed, and opening it would be a guess.
_BARE_HOST = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+(/|$)", re.IGNORECASE)


def resolve_url(raw: str) -> str:
    """Turn what the person typed into something openable, or return empty."""
    text = (raw or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered.startswith(("http://", "https://", "mailto:")):
        return text
    if lowered.startswith(("file:", "javascript:", "data:")):
        return ""
    if _BARE_HOST.match(text):
        return "https://" + text
    return ""


def read_reduce_motion() -> bool:
    """Whether the desktop asks for less movement.

    QtWebEngine does not pass the desktop setting through to CSS, so Dig reads
    it here and tells the interface. GNOME and KDE are both checked, and the
    DIG_REDUCE_MOTION environment variable overrides either.
    """
    env = os.environ.get("DIG_REDUCE_MOTION", "").strip().lower()
    if env in {"1", "true", "yes", "on"}:
        return True
    if env in {"0", "false", "no", "off"}:
        return False

    gsettings = shutil.which("gsettings")
    if gsettings:
        try:
            out = subprocess.run(
                [gsettings, "get", "org.gnome.desktop.interface", "enable-animations"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if out.returncode == 0 and out.stdout.strip() == "false":
                return True
        except (OSError, subprocess.SubprocessError):
            pass

    kdeglobals = Path.home() / ".config" / "kdeglobals"
    try:
        text = kdeglobals.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    for line in text.splitlines():
        if line.replace(" ", "").lower().startswith("animationdurationfactor="):
            try:
                return float(line.split("=", 1)[1].strip()) == 0.0
            except ValueError:
                return False
    return False


def human_size(num: int) -> str:
    """2411724 becomes 2.3 MB. Sizes read the way a person would say them."""
    value = float(num)
    for unit in ("bytes", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "bytes":
                return f"{int(value)} bytes"
            return f"{value:.1f} {unit}".replace(".0 ", " ")
        value /= 1024
    return f"{value:.1f} GB"


def file_chip(name: str) -> str:
    """The short upper case label the file row shows, for example PDF."""
    suffix = Path(name).suffix.lstrip(".").upper()
    if not suffix:
        return "FILE"
    return suffix[:4]


def copy_into_attachments(source: Path, project_id: str) -> Path:
    """Copy a file into this project's folder, never overwriting a neighbor."""
    folder = paths.project_attachments_dir(project_id)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / source.name
    if target.exists():
        stem, suffix = target.stem, target.suffix
        counter = 2
        while target.exists():
            target = folder / f"{stem} ({counter}){suffix}"
            counter += 1
    shutil.copy2(source, target)
    return target


# The shell every PDF is rendered into. The light palette regardless of the
# app's theme, Geist from the bundled files, and no page furniture.
PDF_SHELL = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head><meta charset="utf-8"><title>Dig</title>
<style>/*APP-CSS*/</style>
<style>/*PRINT-CSS*/</style>
</head>
<body><div class="pdf-doc"><!--BODY--></div></body>
</html>"""


def pdf_document(css: str, body_html: str) -> str:
    """The full page a PDF is rendered from. Plain replacement, not format:
    a stylesheet is nothing but braces."""
    return (
        PDF_SHELL.replace("/*APP-CSS*/", css)
        .replace("/*PRINT-CSS*/", PDF_PRINT_CSS)
        .replace("<!--BODY-->", body_html)
    )

PDF_PRINT_CSS = """
@page{size:A4;margin:0}
html,body{height:auto;overflow:visible;background:#fff}
body{padding:0;display:block;background:#fff}
.pdf-doc{padding:0;color:var(--ink)}
.pdf-doc .sheet{border:none;box-shadow:none;padding:0;max-width:none}
.pdf-doc h2.pdf-h{font-size:15px;font-weight:600;letter-spacing:-.01em;margin:22px 0 8px}
.pdf-doc .pdf-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px}
.pdf-doc .pdf-top .o{font-size:20px;font-weight:600;letter-spacing:-.02em}
.pdf-doc .pdf-top .w{font-size:12.5px;color:var(--ink-3);margin-top:2px}
.pdf-doc .pdf-foot{margin-top:22px;padding-top:10px;border-top:1px solid var(--line);font-size:11.5px;color:var(--ink-3);display:flex;justify-content:space-between;gap:16px}
.pdf-doc .box{break-inside:avoid}
.pdf-doc .pc,.pdf-doc .rc{break-inside:avoid}
.pdf-doc .cards{grid-template-columns:repeat(2,1fr)}
.pdf-doc .horizons{grid-template-columns:repeat(2,1fr)}
.pdf-doc *{animation:none!important;transition:none!important}
"""


class Bridge(QObject):
    """Everything the interface asks this computer to do."""

    themeChanged = Signal(str)
    motionChanged = Signal(bool)
    pdfDone = Signal(str)

    def __init__(self, store: StateStore, window=None) -> None:
        super().__init__()
        self._store = store
        self._window = window
        self._pending: str | None = None
        self._first_load: LoadResult | None = None
        self._pdf_pages: list = []
        self._pdf_prof = None

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SAVE_DEBOUNCE_MS)
        self._timer.timeout.connect(self._flush)

        hints = QGuiApplication.styleHints()
        if hints is not None and hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_color_scheme)

    # ------------------------------------------------------------- lifecycle

    def attach_window(self, window) -> None:
        """Give the bridge the window whose geometry it stamps into saves."""
        self._window = window

    def prime(self, result: LoadResult) -> None:
        """Hand the bridge the state that was read before the window opened."""
        self._first_load = result

    def flush(self) -> None:
        """Write anything still waiting. Called before the window closes."""
        if self._timer.isActive():
            self._timer.stop()
        self._flush()

    def _flush(self) -> None:
        payload, self._pending = self._pending, None
        if payload is None:
            return
        try:
            self._store.save(self._with_geometry(payload))
        except Exception as exc:  # a failed save must never take the app down
            print(f"{__app_name__}: could not save: {exc}", flush=True)

    def _with_geometry(self, payload: str) -> str:
        """Stamp the window's size and place into the document as it is written.

        The interface has no idea where its window sits on the desktop, so
        Python fills that part of `ui` in on the way past.
        """
        if self._window is None:
            return payload
        try:
            state = json.loads(payload)
            ui = state.setdefault("ui", {})
            ui["window"] = self._window.geometry_dict()
            return json.dumps(state)
        except Exception:
            return payload

    def _on_color_scheme(self, *_args) -> None:
        self.themeChanged.emit(self.theme())

    # ------------------------------------------------------------------ data

    @Slot(result=str)
    def load(self) -> str:
        """The whole opening picture: state, theme, motion, and any notice."""
        result = self._first_load
        if result is None:
            try:
                result = self._store.load()
            except Exception as exc:
                result = LoadResult(state=None, notice=str(exc), recovered=True)
        self._first_load = None
        return json.dumps(
            {
                "state": result.state,
                "notice": result.notice,
                "recovered": result.recovered,
                "theme": self.theme(),
                "reduceMotion": read_reduce_motion(),
                "dataPath": str(paths.db_path()),
                "version": __version__,
            }
        )

    @Slot(str)
    def save(self, payload: str) -> None:
        """Hold the newest document and write it at most every 300 ms."""
        self._pending = payload
        if not self._timer.isActive():
            self._timer.start()

    @Slot(result=str)
    def theme(self) -> str:
        """The desktop's color scheme, so Follow system means something."""
        hints = QGuiApplication.styleHints()
        if hints is None:
            return "light"
        try:
            return "dark" if hints.colorScheme() == Qt.ColorScheme.Dark else "light"
        except AttributeError:
            return "light"

    @Slot(result=bool)
    def reduceMotion(self) -> bool:
        return read_reduce_motion()

    # ------------------------------------------------------------- the world

    @Slot(str, result=bool)
    def openUrl(self, raw: str) -> bool:
        """Open a link in the browser. Returns false when it is not a link."""
        url = resolve_url(raw)
        if not url:
            return False
        return QDesktopServices.openUrl(QUrl(url))

    @Slot(str, result=bool)
    def openPath(self, raw: str) -> bool:
        """Open a file that Dig is keeping. Returns false when it is gone."""
        path = Path(raw or "").expanduser()
        if not path.exists():
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @Slot(result=bool)
    def openDataFolder(self) -> bool:
        folder = paths.ensure_data_dirs()
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    @Slot()
    def setDesktopFileName(self) -> None:
        """Tell the desktop which launcher this window belongs to."""
        QGuiApplication.setDesktopFileName("dig")

    # ------------------------------------------------------------------ files

    @Slot(str, str, result=str)
    def pickFile(self, project_id: str, file_filter: str) -> str:
        """Choose a file and keep a copy of it inside Dig."""
        chosen, _ = QFileDialog.getOpenFileName(
            self._window,
            "Add a file",
            str(self.documents_dir()),
            file_filter or "All files (*)",
        )
        if not chosen:
            return json.dumps({"ok": False, "reason": "cancelled"})

        source = Path(chosen)
        try:
            stored = copy_into_attachments(source, project_id or "loose")
        except OSError as exc:
            return json.dumps({"ok": False, "reason": str(exc)})

        size = stored.stat().st_size
        return json.dumps(
            {
                "ok": True,
                "name": stored.name,
                "type": file_chip(stored.name),
                "size": size,
                "meta": f"{human_size(size)} · {datetime.now():%b %-d}",
                "stored_path": str(stored),
            }
        )

    # ------------------------------------------------------ export and import

    @Slot(str, result=str)
    def exportJson(self, payload: str) -> str:
        """Write the whole state to a file the person chooses."""
        default = self.documents_dir() / f"dig-export-{datetime.now():%Y-%m-%d}.json"
        chosen, _ = QFileDialog.getSaveFileName(
            self._window, "Export everything", str(default), "JSON file (*.json)"
        )
        if not chosen:
            return json.dumps({"ok": False, "reason": "cancelled"})
        target = Path(chosen)
        if not target.suffix:
            target = target.with_suffix(".json")
        try:
            state = json.loads(payload)
            target.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except (OSError, ValueError) as exc:
            return json.dumps({"ok": False, "reason": str(exc)})
        return json.dumps({"ok": True, "path": str(target), "name": target.name})

    @Slot(result=str)
    def importJson(self) -> str:
        """Read a file back in. The interface asks before replacing anything."""
        chosen, _ = QFileDialog.getOpenFileName(
            self._window,
            "Bring a file back in",
            str(self.documents_dir()),
            "JSON file (*.json);;All files (*)",
        )
        if not chosen:
            return json.dumps({"ok": False, "reason": "cancelled"})
        source = Path(chosen)
        try:
            state = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return json.dumps(
                {"ok": False, "reason": "That file is not something Dig wrote."}
            )
        if not isinstance(state, dict) or "projects" not in state:
            return json.dumps(
                {"ok": False, "reason": "That file is not something Dig wrote."}
            )
        counts = {
            key: len(state.get(key) or [])
            for key in ("groups", "types", "projects", "ideas", "library")
        }
        return json.dumps(
            {"ok": True, "name": source.name, "counts": counts, "state": state}
        )

    # -------------------------------------------------------------------- pdf

    @Slot(str, str)
    def printPdf(self, body_html: str, suggested_name: str) -> str:
        """Render the given markup to a PDF, in the light palette, with Geist.

        The answer comes back on `pdfDone`, because rendering is not instant.
        """
        default = self.documents_dir() / (suggested_name or "dig.pdf")
        chosen, _ = QFileDialog.getSaveFileName(
            self._window, "Save as PDF", str(default), "PDF file (*.pdf)"
        )
        if not chosen:
            self.pdfDone.emit(json.dumps({"ok": False, "reason": "cancelled"}))
            return
        target = Path(chosen)
        if not target.suffix:
            target = target.with_suffix(".pdf")
        self._render_pdf(body_html, target)

    def _render_pdf(self, body_html: str, target: Path) -> None:
        from PySide6.QtGui import QPageLayout, QPageSize
        from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

        css = ""
        try:
            css = (paths.ui_dir() / "app.css").read_text(encoding="utf-8")
        except OSError:
            pass

        document = pdf_document(css, body_html)

        page = QWebEnginePage(self._pdf_profile(), self)
        settings = page.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False
        )
        self._pdf_pages.append(page)  # keep it alive until it has finished

        layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(12, 12, 12, 12),
            QPageLayout.Unit.Millimeter,
        )

        def finished(ok: bool) -> None:
            if not ok:
                self._pdf_finish(page, json.dumps({"ok": False, "reason": "render"}))
                return
            self._await_fonts(page, 0, lambda: self._do_print(page, target, layout))

        page.loadFinished.connect(finished)
        page.setHtml(document, QUrl.fromLocalFile(str(paths.ui_dir()) + "/"))

    def _await_fonts(self, page, tries: int, then) -> None:
        """Give the bundled fonts a moment, so the PDF is never set in a fallback."""
        if tries == 0:
            page.runJavaScript(
                "document.fonts.ready.then(function(){window.__fontsReady=1});0"
            )

        def check(value) -> None:
            if value or tries > 30:
                then()
            else:
                QTimer.singleShot(50, lambda: self._await_fonts(page, tries + 1, then))

        QTimer.singleShot(
            20, lambda: page.runJavaScript("window.__fontsReady||0", check)
        )

    def _do_print(self, page, target: Path, layout) -> None:
        def written(data) -> None:
            payload = {"ok": False, "reason": "nothing came back"}
            if data:
                try:
                    target.write_bytes(bytes(data))
                    payload = {"ok": True, "path": str(target), "name": target.name}
                except OSError as exc:
                    payload = {"ok": False, "reason": str(exc)}
            self._pdf_finish(page, json.dumps(payload))

        page.printToPdf(written, layout)

    def _pdf_finish(self, page, payload: str) -> None:
        if page in self._pdf_pages:
            self._pdf_pages.remove(page)
        page.deleteLater()
        self.pdfDone.emit(payload)

    def _pdf_profile(self):
        from PySide6.QtWebEngineCore import QWebEngineProfile

        if self._pdf_prof is None:
            profile = QWebEngineProfile(self)  # off the record
            if self._window is not None:
                profile.setUrlRequestInterceptor(self._window.interceptor)
            self._pdf_prof = profile
        return self._pdf_prof

    # --------------------------------------------------------------- helpers

    @staticmethod
    def documents_dir() -> Path:
        location = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        return Path(location) if location else Path.home()
