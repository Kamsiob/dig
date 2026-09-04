"""One Dig at a time, and a way to talk to the one that is running.

A second launch does not open a second window. It hands its arguments to the
copy that is already up and exits, which is what makes `dig add "something"`
from a terminal or a keyboard shortcut land in the window you already have open.

The socket is a local one under the user's runtime directory. Nothing listens on
a network port.
"""

from __future__ import annotations

import json
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SOCKET_NAME = "dig-" + str(os.getuid())
CONNECT_MS = 400


def send_to_running(payload: dict) -> bool:
    """Hand arguments to a Dig that is already up. False if there is not one."""
    socket = QLocalSocket()
    socket.connectToServer(SOCKET_NAME)
    if not socket.waitForConnected(CONNECT_MS):
        return False
    socket.write(json.dumps(payload).encode("utf-8"))
    socket.flush()
    socket.waitForBytesWritten(CONNECT_MS)
    socket.disconnectFromServer()
    return True


class Listener(QObject):
    """Hears from a second launch."""

    arrived = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._server = QLocalServer(self)
        # A socket left behind by a Dig that did not shut down cleanly would
        # otherwise stop this one from listening at all.
        QLocalServer.removeServer(SOCKET_NAME)
        self._server.newConnection.connect(self._accept)
        self._server.listen(SOCKET_NAME)

    def _accept(self) -> None:
        connection = self._server.nextPendingConnection()
        if connection is None:
            return

        def read() -> None:
            raw = bytes(connection.readAll())
            connection.disconnectFromServer()
            if not raw:
                return
            try:
                payload = json.loads(raw.decode("utf-8"))
            except ValueError:
                return
            if isinstance(payload, dict):
                self.arrived.emit(payload)

        connection.readyRead.connect(read)

    def close(self) -> None:
        self._server.close()
        QLocalServer.removeServer(SOCKET_NAME)


def parse_args(argv: list[str]) -> dict | None:
    """What `dig add ...` and `dig open ...` mean.

    Returns None when the arguments are not a command, which is the ordinary
    case of someone just launching the app.
    """
    args = [a for a in argv[1:] if a not in ("--version",)]
    if not args:
        return None
    command = args[0]
    if command not in ("add", "open"):
        return None
    rest = args[1:]

    if command == "open":
        name = " ".join(a for a in rest if not a.startswith("-")).strip()
        return {"cmd": "open", "name": name} if name else None

    kind = "auto"
    project = ""
    words: list[str] = []
    index = 0
    while index < len(rest):
        arg = rest[index]
        if arg == "--project":
            index += 1
            project = rest[index] if index < len(rest) else ""
        elif arg.startswith("--project="):
            project = arg.split("=", 1)[1]
        elif arg in ("--log", "--idea", "--bug", "--note", "--link", "--todo"):
            kind = arg[2:]
        else:
            words.append(arg)
        index += 1

    text = " ".join(words).strip()
    if not text:
        return None
    return {"cmd": "add", "text": text, "kind": kind, "project": project}


USAGE = """Dig

  dig                          open Dig
  dig add "text"               put something in the inbox
  dig add "text" --idea        as an idea
  dig add "text" --bug         as a bug
  dig add "text" --note        keep it in the Library
  dig add "text" --link        keep a link in the Library
  dig add "text" --project "Website refresh"
                               onto that project's checklist
  dig add "text" --log --project "Website refresh"
                               as a dated log entry on that project
  dig open "Website refresh"   open that project

A second launch hands its arguments to the Dig you already have open.
"""
