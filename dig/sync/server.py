"""The sync server, which is only ever your own machine talking to your own devices.

It is off until you turn it on. When you do, it binds to loopback and to your
Tailscale address, and to nothing else. If there is no Tailscale interface it
refuses to start and says so, rather than quietly listening somewhere it should
not.

Nothing is published. Tailscale already provides the private network and the
device identity; pairing on top of it is what stops a device on that network
that is not yours from reading anything.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import socket
import socketserver
import threading
import uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import QObject, Signal

from dig import __version__
from dig.store.schema import SCHEMA_VERSION
from dig.store.store import Store, now_iso
from dig.sync import protocol

DEFAULT_PORT = 8787
CODE_MINUTES = 5
PAGE = 500
MAX_BODY = 64 * 1024 * 1024

# Tailscale hands out addresses from the carrier grade NAT range, 100.64.0.0/10.
CGNAT_SECOND = range(64, 128)


def tailscale_addresses() -> list[str]:
    """Every address that looks like this machine's place on its own tailnet."""
    found: list[str] = []
    try:
        from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface
    except Exception:
        return found
    for interface in QNetworkInterface.allInterfaces():
        for entry in interface.addressEntries():
            address = entry.ip()
            if address.protocol() != QAbstractSocket.NetworkLayerProtocol.IPv4Protocol:
                continue
            text = address.toString()
            parts = text.split(".")
            if len(parts) != 4:
                continue
            try:
                first, second = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            if first == 100 and second in CGNAT_SECOND and text not in found:
                found.append(text)
    return found


class _Bound(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, api) -> None:
        self.api = api
        super().__init__(address, handler)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Dig/" + __version__
    sys_version = ""

    # The log goes to Dig's own record, not to the terminal.
    def log_message(self, fmt, *args) -> None:
        pass

    # ---------------------------------------------------------------- helpers

    def _send(self, code: int, payload, kind: str = "application/json") -> None:
        if isinstance(payload, (bytes, bytearray)):
            body = bytes(payload)
        else:
            body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return b""
        return self.rfile.read(length)

    def _token(self) -> str:
        raw = self.headers.get("Authorization") or ""
        return raw[7:].strip() if raw.lower().startswith("bearer ") else raw.strip()

    def do_GET(self) -> None:
        self._route("GET")

    def do_POST(self) -> None:
        self._route("POST")

    def _route(self, method: str) -> None:
        api = self.server.api
        parts = urlparse(self.path)
        path = parts.path.rstrip("/")
        query = parse_qs(parts.query)
        try:
            api.handle(self, method, path, query)
        except Exception as exc:  # a bad request must never take the server down
            api.note("unknown", f"{method} {path}", f"failed: {exc}")
            try:
                self._send(500, {"ok": False, "reason": "Dig could not answer that."})
            except Exception:
                pass


class SyncServer(QObject):
    """Your devices, talking to each other, over your own network."""

    changed = Signal()
    synced = Signal()

    def __init__(self, db_path: Path, history_dir: Path, blobs, parent=None) -> None:
        super().__init__(parent)
        self.db_path = Path(db_path)
        self.history_dir = Path(history_dir)
        self.blobs = blobs
        self.port = DEFAULT_PORT
        self.running = False
        self.bound: list[str] = []
        self.reason = ""
        self.log: list[dict] = []
        self._servers: list[_Bound] = []
        self._threads: list[threading.Thread] = []
        self._code: dict | None = None
        self._lock = threading.Lock()
        # SQLite hands a connection to the thread that made it, and the server
        # answers on several, so each one opens its own.
        self._local = threading.local()

    # ------------------------------------------------------------- the store

    def store(self) -> Store:
        """This thread's own connection. SQLite in WAL mode is happy with several."""
        mine = getattr(self._local, "store", None)
        if mine is None:
            mine = Store(self.db_path, self.history_dir)
            mine.connect()
            self._local.store = mine
        return mine

    # ------------------------------------------------------------- lifecycle

    def start(self, port: int = DEFAULT_PORT) -> dict:
        """Turn it on. Refuses unless there is a Tailscale address to bind to."""
        if self.running:
            return self.status()
        addresses = tailscale_addresses()
        if not addresses:
            self.reason = (
                "Dig could not find a Tailscale address on this machine, so it has not"
                " started. Sync only ever runs over your own private network."
            )
            self.changed.emit()
            return self.status()

        self.port = int(port or DEFAULT_PORT)
        self.bound = []
        for text in ["127.0.0.1"] + addresses:
            try:
                bound = _Bound((text, self.port), _Handler, self)
            except OSError as exc:
                self.reason = f"Dig could not take port {self.port} on {text}. {exc.strerror}."
                continue
            thread = threading.Thread(target=bound.serve_forever, daemon=True)
            thread.start()
            self._servers.append(bound)
            self._threads.append(thread)
            self.bound.append(text)

        if not self.bound:
            if not self.reason:
                self.reason = f"Dig could not take port {self.port}."
            self.changed.emit()
            return self.status()

        self.running = True
        self.reason = ""
        self.changed.emit()
        return self.status()

    def stop(self) -> dict:
        for bound in self._servers:
            try:
                bound.shutdown()
                bound.server_close()
            except Exception:
                pass
        self._servers = []
        self._threads = []
        self.running = False
        self.bound = []
        self._code = None
        mine = getattr(self._local, "store", None)
        if mine is not None:
            mine.close()
            self._local.store = None
        self.changed.emit()
        return self.status()

    def status(self) -> dict:
        return {
            "running": self.running,
            "port": self.port,
            "bound": list(self.bound),
            "reason": self.reason,
            "tailscale": tailscale_addresses(),
            "devices": self.devices(),
            "code": self._code_public(),
            "log": self.log[-40:],
        }

    # -------------------------------------------------------------- pairing

    def make_code(self) -> dict:
        """A one time code, good for five minutes, usable once."""
        if not self.running:
            return {"ok": False, "reason": "Turn sync on first."}
        address = next((a for a in self.bound if a != "127.0.0.1"), self.bound[0])
        code = "-".join(secrets.token_hex(2).upper() for _ in range(3))
        self._code = {
            "code": code,
            "until": (datetime.now() + timedelta(minutes=CODE_MINUTES)).isoformat(),
            "address": address,
            "port": self.port,
        }
        self.changed.emit()
        return {"ok": True, **(self._code_public() or {})}

    def _code_public(self) -> dict | None:
        if not self._code:
            return None
        if datetime.fromisoformat(self._code["until"]) < datetime.now():
            self._code = None
            return None
        payload = {
            "v": 1, "address": self._code["address"], "port": self._code["port"],
            "code": self._code["code"], "name": self.store().device_name(),
        }
        return {
            "code": self._code["code"],
            "until": self._code["until"],
            "address": self._code["address"],
            "port": self._code["port"],
            "pairing": json.dumps(payload, separators=(",", ":")),
        }

    def devices(self) -> list[dict]:
        try:
            conn = self.store().connect()
            rows = conn.execute(
                "SELECT id, name, paired_at, last_synced, revoked FROM devices"
                " WHERE is_self = 0 ORDER BY paired_at DESC"
            ).fetchall()
        except Exception:
            return []
        return [dict(r) for r in rows]

    def revoke(self, device_id: str) -> bool:
        conn = self.store().connect()
        with conn:
            conn.execute(
                "UPDATE devices SET revoked = 1, token = NULL WHERE id = ? AND is_self = 0",
                (device_id,),
            )
        self.note(device_id, "was revoked", "its token no longer works")
        self.changed.emit()
        return True

    def _device_for(self, token: str):
        if not token:
            return None
        conn = self.store().connect()
        return conn.execute(
            "SELECT * FROM devices WHERE token = ? AND revoked = 0 AND is_self = 0", (token,)
        ).fetchone()

    def note(self, device: str, what: str, outcome: str) -> None:
        with self._lock:
            self.log.append(
                {"at": now_iso(), "device": device, "what": what, "outcome": outcome}
            )
            if len(self.log) > 400:
                self.log = self.log[-200:]

    # ----------------------------------------------------------- the requests

    def handle(self, http, method: str, path: str, query: dict) -> None:
        if path == "/v1/hello" and method == "GET":
            http._send(200, {
                "app": "Dig", "version": __version__, "schema": SCHEMA_VERSION,
                "device": self.store().device_id, "name": self.store().device_name(),
            })
            return

        if path == "/v1/pair" and method == "POST":
            self._pair(http)
            return

        device = self._device_for(http._token())
        if device is None:
            self.note("unknown", f"{method} {path}", "refused, not paired")
            http._send(401, {"ok": False, "reason": "not paired"})
            return

        if path == "/v1/state" and method == "GET":
            self.note(device["name"], "took a full snapshot", "ok")
            http._send(200, {
                "ok": True, "state": self.store().load().state,
                "cursor": self.store().meta()["cursor"], "schema": SCHEMA_VERSION,
            })
            return

        if path == "/v1/changes" and method == "GET":
            try:
                since = int((query.get("since") or ["0"])[0])
            except ValueError:
                since = 0
            rows = self.store().changes_since(since, PAGE)
            cursor = rows[-1]["seq"] if rows else since
            self.note(device["name"], f"pulled {len(rows)} changes", "ok")
            http._send(200, {"ok": True, "changes": rows, "cursor": cursor,
                             "more": len(rows) == PAGE})
            return

        if path == "/v1/push" and method == "POST":
            self._push(http, device)
            return

        if path.startswith("/v1/blobs/"):
            self._blob(http, method, path, device)
            return

        http._send(404, {"ok": False, "reason": "no such thing here"})

    def _pair(self, http) -> None:
        try:
            body = json.loads(http._body().decode("utf-8"))
        except Exception:
            http._send(400, {"ok": False, "reason": "unreadable"})
            return
        live = self._code_public()
        if not live or body.get("code") != live["code"]:
            self.note(body.get("name", "unknown"), "pairing", "refused, wrong or expired code")
            http._send(403, {"ok": False, "reason": "that code is wrong or has expired"})
            return
        asked = int(body.get("schema") or 0)
        if asked and asked != SCHEMA_VERSION:
            self.note(body.get("name", "unknown"), "pairing", "refused, different version")
            http._send(409, {"ok": False, "reason": "that device speaks a different version of Dig"})
            return
        token = secrets.token_urlsafe(32)
        device_id = body.get("device") or str(uuid.uuid4())
        conn = self.store().connect()
        with conn:
            conn.execute(
                "INSERT INTO devices (id, name, is_self, token, paired_at, revoked)"
                " VALUES (?, ?, 0, ?, ?, 0)"
                " ON CONFLICT(id) DO UPDATE SET name=excluded.name, token=excluded.token,"
                " paired_at=excluded.paired_at, revoked=0",
                (device_id, body.get("name") or "a device", token, now_iso()),
            )
        self._code = None  # single use
        self.note(body.get("name", device_id), "pairing", "paired")
        self.changed.emit()
        http._send(200, {"ok": True, "token": token, "device": self.store().device_id,
                         "schema": SCHEMA_VERSION})

    def _push(self, http, device) -> None:
        try:
            body = json.loads(http._body().decode("utf-8"))
        except Exception:
            http._send(400, {"ok": False, "reason": "unreadable"})
            return
        asked = int(body.get("schema") or SCHEMA_VERSION)
        if asked != SCHEMA_VERSION:
            self.note(device["name"], "pushed changes", "refused, different version")
            http._send(409, {"ok": False, "reason": "that device speaks a different version of Dig"})
            return
        outcomes = protocol.apply_batch(self.store(), body.get("changes") or [])
        conn = self.store().connect()
        with conn:
            conn.execute("UPDATE devices SET last_synced = ? WHERE id = ?",
                         (now_iso(), device["id"]))
        self.note(device["name"], f"pushed {len(outcomes)} changes", "ok")
        self.synced.emit()
        http._send(200, {
            "ok": True,
            "results": [
                {"id": o.record_id, "collection": o.collection, "result": o.result, "why": o.why}
                for o in outcomes
            ],
            "cursor": self.store().meta()["cursor"],
        })

    def _blob(self, http, method: str, path: str, device) -> None:
        rest = path[len("/v1/blobs/"):]
        upload = rest.endswith("/upload")
        sha = rest[:-len("/upload")] if upload else rest
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            http._send(400, {"ok": False, "reason": "that is not a hash"})
            return

        if method == "GET" and not upload:
            if not self.blobs.has(sha):
                http._send(404, {"ok": False, "reason": "no such file"})
                return
            data = self.blobs.read(sha)
            self.note(device["name"], f"took a file, {len(data)} bytes", "ok")
            http._send(200, data, "application/octet-stream")
            return

        if method == "POST" and upload:
            data = http._body()
            if hashlib.sha256(data).hexdigest() != sha:
                self.note(device["name"], "sent a file", "refused, hash did not match")
                http._send(400, {"ok": False, "reason": "those bytes are not that hash"})
                return
            if not self.blobs.has(sha):
                self.blobs.put_bytes(data, sha)
            self.note(device["name"], f"sent a file, {len(data)} bytes", "ok")
            self.synced.emit()
            http._send(200, {"ok": True, "sha256": sha, "size": len(data)})
            return

        http._send(405, {"ok": False, "reason": "not something you can do here"})
