"""Start Dig.

Reads the state, opens one window, and hands the interface a bridge back to
this computer.
"""

from __future__ import annotations

import os
import sys

from dig import __app_name__, __version__, paths


def _configure_engine() -> None:
    """Settings that have to be in place before Qt starts up."""
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    additions = [
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-domain-reliability",
        "--disable-sync",
        "--no-pings",
        "--disable-features=Translate,OptimizationHints,MediaRouter",
    ]
    for flag in additions:
        if flag.split("=")[0] not in flags:
            flags = f"{flags} {flag}".strip()
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = flags
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--version" in argv:
        print(f"{__app_name__} {__version__}")
        return 0

    _configure_engine()

    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtWidgets import QApplication

    from dig.bridge import Bridge
    from dig.migrate_v1 import migrate_if_needed
    from dig.storage import StateStore
    from dig.window import MainWindow

    QApplication.setApplicationName(__app_name__)
    QApplication.setApplicationDisplayName(__app_name__)
    QApplication.setOrganizationName("Kamsiob")
    QApplication.setApplicationVersion(__version__)
    # KDE Plasma on Wayland uses this to group the window with its launcher.
    QGuiApplication.setDesktopFileName("dig")

    app = QApplication(argv)

    icon_path = paths.project_root() / "assets" / "icons" / "dig-256.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    paths.ensure_data_dirs()
    store = StateStore(paths.db_path(), paths.history_dir())

    migration_notice = migrate_if_needed(store)
    result = store.load()
    if migration_notice and not result.notice:
        result.notice = migration_notice

    bridge = Bridge(store)
    window = MainWindow(bridge)
    bridge.attach_window(window)
    bridge.prime(result)

    saved_ui = (result.state or {}).get("ui") or {}
    window.apply_geometry(saved_ui.get("window"))
    window.load_ui()
    window.show()

    return app.exec()
