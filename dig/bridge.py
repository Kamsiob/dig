"""The bridge between the web interface and this computer.

Everything the interface cannot do on its own goes through here: reading and
writing the state document, copying files into the managed attachments folder,
exporting and importing, rendering PDFs, opening links and folders, and
reporting the desktop's color scheme and reduce-motion setting.

Nothing in this file opens a socket. Dig makes no network calls.
"""

from __future__ import annotations

import base64
import binascii
import csv
import io
import json
import os
import re
import shutil
import subprocess
import zipfile
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
from dig import csvin
from dig.backup import (
    read_backup,
    read_manifest,
    scheduled_is_due,
    scheduled_name,
    trim_scheduled,
    write_backup,
)
from dig.store import BlobStore, LoadResult, Store
from dig.store.schema import SCHEMA_VERSION
from dig.store.blobs import LARGE_FILE_BYTES

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


def _unique_in_zip(name: str, used: set) -> str:
    """Two files of the same name both get into the archive."""
    safe = Path(name).name or "file"
    if safe not in used:
        used.add(safe)
        return safe
    stem, suffix = Path(safe).stem, Path(safe).suffix
    counter = 2
    while f"{stem} ({counter}){suffix}" in used:
        counter += 1
    picked = f"{stem} ({counter}){suffix}"
    used.add(picked)
    return picked


def _qr_svg(payload: str) -> str:
    """The pairing details as a QR code, drawn here and shown here."""
    try:
        import io

        import segno

        code = segno.make(payload, error="m")
        buffer = io.BytesIO()
        code.save(buffer, kind="svg", scale=5, border=2,
                  dark="#0E1421", light="#FFFFFF", xmldecl=False, svgns=True)
        return buffer.getvalue().decode("utf-8")
    except Exception:
        return ""


def _inside_digs_own(path: Path) -> bool:
    """Whether a path is one of Dig's own files, rather than anything at all."""
    roots = (paths.blobs_dir(), paths.attachments_dir(), paths.history_dir())
    for root in roots:
        try:
            path.relative_to(root.resolve())
            return True
        except (ValueError, OSError):
            continue
    return False


def _looks_like_dig(state) -> bool:
    """Whether a file is shaped like a document Dig wrote."""
    if not isinstance(state, dict):
        return False
    for key in ("groups", "types", "projects", "ideas", "inbox", "library", "activity"):
        if key in state and not isinstance(state[key], list):
            return False
    if "projects" not in state:
        return False
    for project in state["projects"]:
        if not isinstance(project, dict) or not project.get("id"):
            return False
    return True


def safe_id(value: str) -> str:
    """An id that can only ever name a folder, never a path."""
    cleaned = "".join(c for c in str(value or "") if c.isalnum() or c in "-_")
    return cleaned[:64] or "loose"


def copy_into_attachments(source: Path, project_id: str) -> Path:
    """Copy a file into this project's folder, never overwriting a neighbor."""
    folder = paths.project_attachments_dir(safe_id(project_id))
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


def _tilde(path: Path) -> str:
    """A path with the home folder written the way a person writes it.

    Settings puts this on screen, and the design writes it as
    ~/.local/share/dig/dig.db. Spelling out the home folder would also put
    someone's user name on screen every time they shared their window.
    """
    try:
        return "~/" + str(Path(path).relative_to(Path.home()))
    except ValueError:
        return str(path)


class Bridge(QObject):
    """Everything the interface asks this computer to do."""

    themeChanged = Signal(str)
    motionChanged = Signal(bool)
    pdfDone = Signal(str)
    saveFailed = Signal(str)
    syncedFromElsewhere = Signal()

    def __init__(self, store: Store, window=None) -> None:
        super().__init__()
        self._store = store
        self._window = window
        self._pending: str | None = None
        # How far the oplog had got when the interface was handed its document.
        # Anything another device wrote after this the interface has never seen,
        # so a save of that document must not read as having deleted it. Only a
        # load or a reload moves this, because only those two hand the interface
        # a document.
        self._document_cursor = 0
        self._pending_cursor = 0
        self._first_load: LoadResult | None = None
        self._pdf_pages: list = []
        self._pdf_prof = None
        self._save_broken = False
        self._pending_restore = None
        self._pending_csv = ""
        self._sync = None
        self._motion = read_reduce_motion()
        self.blobs = BlobStore(paths.blobs_dir())
        self._blob_mimes: dict[str, str] = {}

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SAVE_DEBOUNCE_MS)
        self._timer.timeout.connect(self._flush)

        hints = QGuiApplication.styleHints()
        if hints is not None and hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_color_scheme)

    # ------------------------------------------------------------- lifecycle

    @property
    def store(self):
        return self._store

    def attach_window(self, window) -> None:
        """Give the bridge the window whose geometry it stamps into saves."""
        self._window = window

    def prime(self, result: LoadResult) -> None:
        """Hand the bridge the state that was read before the window opened."""
        self._first_load = result

    def has_pending(self) -> bool:
        """Whether the interface has handed over a change not yet written."""
        return self._pending is not None

    def flush(self) -> None:
        """Write anything still waiting. Called before the window closes."""
        if self._timer.isActive():
            self._timer.stop()
        self._flush()

    def _flush(self) -> None:
        payload, self._pending = self._pending, None
        cursor = self._pending_cursor
        if payload is None:
            return
        try:
            self._store.save_state(json.loads(self._with_geometry(payload)), cursor)
            if self._save_broken:
                self._save_broken = False
                self.saveFailed.emit("")
        except Exception as exc:  # a failed save must never take the app down
            print(f"{__app_name__}: could not save: {exc}", flush=True)
            self._pending = payload  # hold it; the next attempt may get through
            self._pending_cursor = cursor
            if not self._save_broken:
                self._save_broken = True
                self.saveFailed.emit(
                    "Dig is not able to write to "
                    f"{paths.db_path()}. Your changes are only in this window."
                )

    @Slot(int)
    def tookDocument(self, cursor: int) -> None:
        """The interface says it is now holding the document read at this point.

        It has to say so itself. Stamping this when the document was handed
        over would leave a window in which the interface still holds the old
        one and a save of it would read as having deleted whatever arrived in
        between.
        """
        self._document_cursor = int(cursor or 0)

    def _cursor_now(self) -> int:
        try:
            return int(self._store.meta().get("cursor") or 0)
        except Exception:
            return 0

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
                "cursor": self._cursor_now(),
                "notice": result.notice,
                "recovered": result.recovered,
                "theme": self.theme(),
                "reduceMotion": read_reduce_motion(),
                "dataPath": _tilde(paths.db_path()),
                "version": __version__,
                "device": result.meta.get("device_name", ""),
                "schema": result.meta.get("schema_version", 0),
            }
        )

    @Slot(str)
    def save(self, payload: str) -> None:
        """Hold the newest document and write it at most every 300 ms.

        The cursor is taken now, not when it is written, because that is what
        this document knows. A change arriving from another device in between
        would otherwise look like something this document had deleted.
        """
        self._pending = payload
        self._pending_cursor = self._document_cursor
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
        self._motion = read_reduce_motion()
        return self._motion

    @Slot(float, result=bool)
    def setZoom(self, factor: float) -> bool:
        """Scale the whole interface. Settings, Appearance, Text size.

        The interface sizes its text in pixels throughout, so a larger base
        size alone would move a few things and leave the rest. The web engine's
        own zoom scales the words, the boxes and the space between them
        together, which is what a person means by larger text.
        """
        window = self._window
        page = getattr(window, "page", None)
        if page is None:
            return False
        page.setZoomFactor(max(0.5, min(3.0, float(factor) or 1.0)))
        return True

    def recheck_motion(self) -> None:
        """Re-read the desktop's reduce-motion setting and tell the interface.

        Called when the window is activated, which is when someone coming back
        from their system settings would expect to see it take effect.
        """
        current = read_reduce_motion()
        if current != self._motion:
            self._motion = current
            self.motionChanged.emit(current)

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
        """Open a file Dig is keeping. Only ever one of Dig's own."""
        try:
            path = Path(raw or "").expanduser().resolve()
        except OSError:
            return False
        if not path.is_file() or not _inside_digs_own(path):
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
        except (OSError, ValueError):
            return json.dumps(
                {"ok": False, "reason": "Dig could not keep a copy of that file."}
            )

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


    # ------------------------------------------------------------------ files

    @Slot(str, str, result=str)
    def pickFiles(self, project_id: str, group_id: str) -> str:
        """Choose one or more files and keep a copy of each inside Dig."""
        chosen, _ = QFileDialog.getOpenFileNames(
            self._window, "Add files", str(self.documents_dir()), "All files (*)"
        )
        if not chosen:
            return json.dumps({"ok": False, "reason": "cancelled"})
        return json.dumps(self._take_in([Path(c) for c in chosen], project_id, group_id))

    @Slot(str, str, str, result=str)
    def addPaths(self, paths_json: str, project_id: str, group_id: str) -> str:
        """Take in files that were dropped onto the window."""
        try:
            wanted = [Path(p) for p in json.loads(paths_json)]
        except (TypeError, ValueError):
            return json.dumps({"ok": False, "reason": "nothing usable was dropped"})
        return json.dumps(self._take_in(wanted, project_id, group_id))

    @Slot(str, str, str, str, result=str)
    def addPasted(self, name: str, data_url: str, project_id: str, group_id: str) -> str:
        """Take in something pasted from the clipboard."""
        try:
            head, _, payload = data_url.partition(",")
            raw = base64.b64decode(payload) if "base64" in head else payload.encode("utf-8")
        except (ValueError, binascii.Error):
            return json.dumps({"ok": False, "reason": "that could not be read"})
        if not raw:
            return json.dumps({"ok": False, "reason": "there was nothing to paste"})
        stored = self.blobs.put_bytes(raw, name or "Pasted file")
        return json.dumps({"ok": True, "files": [self._file_record(stored, project_id, group_id)]})

    def _take_in(self, sources: list, project_id: str, group_id: str) -> dict:
        kept, refused, large = [], [], []
        for source in sources:
            if not source.is_file():
                refused.append(source.name)
                continue
            try:
                size = source.stat().st_size
                stored = self.blobs.put(source)
            except OSError:
                refused.append(source.name)
                continue
            if size > LARGE_FILE_BYTES:
                large.append(source.name)
            kept.append(self._file_record(stored, project_id, group_id))
        return {"ok": bool(kept), "files": kept, "refused": refused, "large": large}

    def _file_record(self, stored, project_id: str, group_id: str) -> dict:
        return {
            "sha256": stored.sha256,
            "name": stored.name,
            "type": stored.ext,
            "mime": stored.mime,
            "size": stored.size,
            "added_at": datetime.now().isoformat(timespec="seconds"),
            "project_id": project_id or None,
            "group_id": group_id or None,
            "deduplicated": stored.deduplicated,
        }

    @Slot(str, str, result=str)
    def saveCopy(self, sha256: str, name: str) -> str:
        """Write the exact original bytes somewhere the person chooses."""
        if not self.blobs.has(sha256):
            return json.dumps({"ok": False, "reason": "Dig does not have those bytes."})
        chosen, _ = QFileDialog.getSaveFileName(
            self._window, "Save a copy", str(self.documents_dir() / (name or "file")), "All files (*)"
        )
        if not chosen:
            return json.dumps({"ok": False, "reason": "cancelled"})
        try:
            self.blobs.copy_out(sha256, Path(chosen))
        except OSError:
            return json.dumps(
                {"ok": False, "reason": "Dig could not write there. Pick another folder."}
            )
        return json.dumps({"ok": True, "name": Path(chosen).name})

    @Slot(str, str, result=str)
    def saveAllFiles(self, files_json: str, suggested: str) -> str:
        """Write every file of one project or group as a zip, with a manifest."""
        try:
            wanted = json.loads(files_json)
        except (TypeError, ValueError):
            wanted = []
        if not wanted:
            return json.dumps({"ok": False, "reason": "There are no files to save."})
        chosen, _ = QFileDialog.getSaveFileName(
            self._window,
            "Save all files",
            str(self.documents_dir() / f"{suggested or 'files'}.zip"),
            "Zip archive (*.zip)",
        )
        if not chosen:
            return json.dumps({"ok": False, "reason": "cancelled"})
        target = Path(chosen)
        if target.suffix.lower() != ".zip":
            target = target.with_suffix(".zip")

        rows = [["name", "document id", "version", "size", "added", "sha256"]]
        try:
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                used: set[str] = set()
                for item in wanted:
                    sha = item.get("sha256") or ""
                    if not self.blobs.has(sha):
                        continue
                    name = _unique_in_zip(item.get("name") or sha, used)
                    archive.writestr(name, self.blobs.read(sha))
                    rows.append([
                        name, item.get("doc_id") or "", item.get("version") or "",
                        str(item.get("size") or 0), item.get("added_at") or "", sha,
                    ])
                buffer = io.StringIO()
                csv.writer(buffer).writerows(rows)
                archive.writestr("manifest.csv", buffer.getvalue())
        except OSError:
            return json.dumps(
                {"ok": False, "reason": "Dig could not write there. Pick another folder."}
            )
        return json.dumps({"ok": True, "name": target.name, "count": len(rows) - 1})

    @Slot(str, str, result=str)
    def viewUrl(self, sha256: str, name: str) -> str:
        """A file:// URL the viewer can point an img, embed, or video at."""
        if not sha256 or not self.blobs.has(sha256):
            return ""
        return QUrl.fromLocalFile(str(self.blobs.view_path(sha256, name or ""))).toString()

    @Slot(str, result=str)
    def readText(self, sha256: str) -> str:
        """The text of a text file, for the viewer. Never more than 2 MB."""
        if not sha256 or not self.blobs.has(sha256):
            return json.dumps({"ok": False, "reason": "Dig does not have those bytes."})
        if self.blobs.size_of(sha256) > 2 * 1024 * 1024:
            return json.dumps(
                {"ok": False, "reason": "That file is too big to show here. Open it with the system app."}
            )
        try:
            text = self.blobs.read(sha256).decode("utf-8", "replace")
        except OSError:
            return json.dumps({"ok": False, "reason": "Dig could not read that one."})
        return json.dumps({"ok": True, "text": text})

    def mime_for_blob(self, sha256: str) -> str:
        """The type the interface recorded for these bytes, if it told us one."""
        return self._blob_mimes.get(sha256, "")

    @Slot(str, str)
    def rememberMime(self, sha256: str, mime: str) -> None:
        if sha256 and mime:
            self._blob_mimes[sha256] = mime

    @Slot(str, result=bool)
    def openBlob(self, sha256: str) -> bool:
        """Hand a file to whatever the desktop opens that kind with."""
        if not self.blobs.has(sha256):
            return False
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.blobs.path_for(sha256))))

    @Slot(str, result=bool)
    def revealBlob(self, sha256: str) -> bool:
        """Open the folder the bytes are kept in."""
        if not self.blobs.has(sha256):
            return False
        return QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.blobs.path_for(sha256).parent))
        )

    @Slot(str, result=str)
    def storage(self, referenced_json: str) -> str:
        """What the files are costing, and how much of it nothing points at."""
        try:
            referenced = set(json.loads(referenced_json) or [])
        except (TypeError, ValueError):
            referenced = set()
        loose = self.blobs.unreferenced(referenced)
        return json.dumps(
            {
                "total": self.blobs.total_size(),
                "totalHuman": human_size(self.blobs.total_size()),
                "count": len(self.blobs.every()),
                "loose": len(loose),
                "looseSize": sum(self.blobs.size_of(sha) for sha in loose),
                "looseHuman": human_size(sum(self.blobs.size_of(sha) for sha in loose)),
                "path": str(paths.blobs_dir()),
            }
        )

    @Slot(str, result=str)
    def cleanUp(self, referenced_json: str) -> str:
        """Remove only blobs that nothing at all points at."""
        try:
            referenced = set(json.loads(referenced_json) or [])
        except (TypeError, ValueError):
            return json.dumps({"ok": False, "reason": "Dig could not tell what is in use."})
        freed = 0
        removed = 0
        for sha in self.blobs.unreferenced(referenced):
            freed += self.blobs.remove(sha)
            removed += 1
        return json.dumps({"ok": True, "removed": removed, "freed": human_size(freed)})

    # ------------------------------------------------------------------ sync

    def sync_server(self):
        """The server, made the first time it is asked for. It starts off."""
        if self._sync is None:
            from dig.sync import SyncServer

            self._sync = SyncServer(paths.db_path(), paths.history_dir(), self.blobs, self)
            self._sync.synced.connect(lambda: self.syncedFromElsewhere.emit())
        return self._sync

    @Slot(result=str)
    def syncStatus(self) -> str:
        return json.dumps(self.sync_server().status(), default=str)

    @Slot(int, result=str)
    def syncStart(self, port: int) -> str:
        return json.dumps(self.sync_server().start(port or 8787), default=str)

    @Slot(result=str)
    def syncStop(self) -> str:
        return json.dumps(self.sync_server().stop(), default=str)

    @Slot(result=str)
    def syncPair(self) -> str:
        """A one time code, and the same thing as a QR code to point a phone at."""
        made = self.sync_server().make_code()
        if made.get("ok") and made.get("pairing"):
            made["qr"] = _qr_svg(made["pairing"])
        return json.dumps(made, default=str)

    @Slot(str, result=bool)
    def syncRevoke(self, device_id: str) -> bool:
        return self.sync_server().revoke(device_id)

    @Slot(result=str)
    def syncConflicts(self) -> str:
        from dig.sync import protocol

        return json.dumps({"ok": True, "rows": protocol.open_conflicts(self._store)}, default=str)

    @Slot(str, result=str)
    def syncConflictsSeen(self, ids_json: str) -> str:
        from dig.sync import protocol

        try:
            ids = json.loads(ids_json) or []
        except ValueError:
            ids = []
        return json.dumps({"ok": True, "count": protocol.mark_conflicts_seen(self._store, ids)})

    @Slot(result=str)
    def reload(self) -> str:
        """The document as it is on disk right now, after a sync brought things in.

        Anything still waiting to be written goes down first. Without that, a
        change made a moment ago would be read over by the version that was on
        disk before it.
        """
        self.flush()
        try:
            state = self._store.load().state
        except Exception:
            return json.dumps({"ok": False, "reason": "Dig could not read it back."})
        return json.dumps(
            {"ok": True, "state": state, "cursor": self._cursor_now()}, default=str
        )

    # --------------------------------------------------- backup and restore

    @Slot(str, result=str)
    def backupEverything(self, payload: str) -> str:
        """One zip with the whole document and every file it points at."""
        default = self.documents_dir() / f"dig-backup-{datetime.now():%Y-%m-%d}.zip"
        chosen, _ = QFileDialog.getSaveFileName(
            self._window, "Back up everything", str(default), "Zip archive (*.zip)"
        )
        if not chosen:
            return json.dumps({"ok": False, "reason": "cancelled"})
        try:
            made = write_backup(Path(chosen), json.loads(payload), self.blobs)
        except OSError:
            return json.dumps(
                {"ok": False, "reason": "Dig could not write there. Pick another folder."}
            )
        except ValueError:
            return json.dumps({"ok": False, "reason": "Dig could not put that together."})
        return json.dumps(
            {
                "ok": True, "name": made.path.name, "size": human_size(made.size),
                "projects": made.projects, "blobs": made.blobs,
            }
        )

    @Slot(result=str)
    def chooseBackup(self) -> str:
        """Pick a backup and say what is in it, without restoring anything."""
        chosen, _ = QFileDialog.getOpenFileName(
            self._window, "Restore from a backup", str(self.documents_dir()),
            "Zip archive (*.zip);;All files (*)",
        )
        if not chosen:
            return json.dumps({"ok": False, "reason": "cancelled"})
        manifest = read_manifest(Path(chosen))
        if manifest is None:
            return json.dumps(
                {"ok": False, "reason": "That is not a backup Dig made."}
            )
        if int(manifest.get("schema") or 0) > SCHEMA_VERSION:
            return json.dumps(
                {"ok": False, "reason": "That backup came from a newer Dig than this one."}
            )
        self._pending_restore = Path(chosen)
        manifest["path"] = str(chosen)
        manifest["name"] = Path(chosen).name
        manifest["ok"] = True
        return json.dumps(manifest)

    @Slot(str, result=str)
    def restoreBackup(self, current_payload: str) -> str:
        """Put a backup back, after taking one of what is here first."""
        source = getattr(self, "_pending_restore", None)
        if source is None or not Path(source).is_file():
            return json.dumps({"ok": False, "reason": "Pick a backup first."})
        safety = paths.backups_dir() / f"before-restore-{datetime.now():%Y%m%d-%H%M%S}.zip"
        try:
            safety.parent.mkdir(parents=True, exist_ok=True)
            write_backup(safety, json.loads(current_payload), self.blobs)
        except Exception:
            return json.dumps(
                {"ok": False, "reason": "Dig could not back up what is here first, so it stopped."}
            )
        try:
            state, blobs = read_backup(Path(source))
            for sha, data in blobs:
                if not self.blobs.has(sha):
                    self.blobs.put_bytes(data, sha)
        except Exception:
            return json.dumps(
                {"ok": False, "reason": "That backup could not be read. Nothing was changed."}
            )
        self._pending_restore = None
        return json.dumps({"ok": True, "state": state, "safety": safety.name})

    @Slot(str, str, str, result=str)
    def scheduledBackup(self, payload: str, folder: str, cadence: str) -> str:
        """Make the quiet backup if one is owed. Off unless a folder is set."""
        if not folder or cadence not in ("daily", "weekly"):
            return json.dumps({"ok": False, "reason": "off"})
        place = Path(folder).expanduser()
        if not scheduled_is_due(place, cadence):
            return json.dumps({"ok": False, "reason": "not due"})
        try:
            place.mkdir(parents=True, exist_ok=True)
            made = write_backup(place / scheduled_name(), json.loads(payload), self.blobs)
            trim_scheduled(place)
        except Exception:
            return json.dumps(
                {"ok": False, "reason": "Dig could not write the scheduled backup there."}
            )
        return json.dumps({"ok": True, "name": made.path.name})

    @Slot(result=str)
    def chooseBackupFolder(self) -> str:
        chosen = QFileDialog.getExistingDirectory(
            self._window, "Where should the scheduled backups go?", str(self.documents_dir())
        )
        return json.dumps({"ok": bool(chosen), "path": chosen})

    # ---------------------------------------------------------- csv import

    @Slot(str, str, result=str)
    def chooseCsv(self, kind: str, mapping_json: str) -> str:
        """Pick a CSV and say what Dig would make of it, without making it."""
        chosen, _ = QFileDialog.getOpenFileName(
            self._window, "Import from CSV", str(self.documents_dir()),
            "CSV file (*.csv);;All files (*)",
        )
        if not chosen:
            return json.dumps({"ok": False, "reason": "cancelled"})
        try:
            text = Path(chosen).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return json.dumps({"ok": False, "reason": "Dig could not read that file."})
        self._pending_csv = text
        result = csvin.preview(text, kind)
        result["name"] = Path(chosen).name
        return json.dumps(result)

    @Slot(str, str, result=str)
    def previewCsv(self, kind: str, mapping_json: str) -> str:
        """The same preview again, with the columns mapped a different way."""
        text = getattr(self, "_pending_csv", "")
        if not text:
            return json.dumps({"ok": False, "reason": "Pick a file first."})
        try:
            mapping = json.loads(mapping_json)
        except ValueError:
            mapping = None
        return json.dumps(csvin.preview(text, kind, mapping))

    @Slot(str, str, result=str)
    def readCsv(self, kind: str, mapping_json: str) -> str:
        """Every row, mapped, for the interface to turn into records."""
        text = getattr(self, "_pending_csv", "")
        if not text:
            return json.dumps({"ok": False, "reason": "Pick a file first."})
        try:
            mapping = json.loads(mapping_json)
        except ValueError:
            return json.dumps({"ok": False, "reason": "Dig lost track of the columns."})
        rows = csvin.read_all(text, kind, mapping)
        self._pending_csv = ""
        self._sync = None
        return json.dumps({"ok": True, "rows": rows})

    # ------------------------------------------------------ recently deleted

    @Slot(result=str)
    def recentlyDeleted(self) -> str:
        """What has been deleted in the last thirty days, newest first."""
        rows = []
        for row in self._store.deleted_since(30):
            rows.append(
                {
                    "collection": row["collection"],
                    "id": row["id"],
                    "name": row.get("name") or row.get("text") or row.get("title")
                    or row.get("v") or "(no name)",
                    "when": row.get("deleted_at") or "",
                }
            )
        return json.dumps({"ok": True, "rows": rows})

    @Slot(str, str, result=str)
    def restoreDeleted(self, collection: str, record_id: str) -> str:
        """Bring one deleted thing back, and hand the whole document back."""
        try:
            found = self._store.restore(collection, record_id)
        except Exception:
            return json.dumps({"ok": False, "reason": "Dig could not bring that back."})
        if not found:
            return json.dumps({"ok": False, "reason": "That one is no longer there to restore."})
        return json.dumps({"ok": True, "state": self._store.load().state})

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
        except OSError:
            return json.dumps(
                {"ok": False, "reason": "Dig could not write there. Pick another folder."}
            )
        except ValueError:
            return json.dumps(
                {"ok": False, "reason": "Dig could not put that together to export."}
            )
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
        if not _looks_like_dig(state):
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
                self._pdf_finish(
                    page,
                    json.dumps({"ok": False, "reason": "Dig could not lay the PDF out."}),
                )
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
            payload = {"ok": False, "reason": "Dig could not lay the PDF out."}
            if data:
                try:
                    target.write_bytes(bytes(data))
                    payload = {"ok": True, "path": str(target), "name": target.name}
                except OSError:
                    payload = {
                        "ok": False,
                        "reason": "Dig could not write there. Pick another folder.",
                    }
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
