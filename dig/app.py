"""Start Dig."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from dig import __version__
from dig.storage import Store
from dig.storage.schema import SchemaTooNewError
from dig.theme import APPEARANCE_KEY, SYSTEM_MODE, ThemeManager, register_fonts
from dig.ui.window import MainWindow

DESKTOP_FILE_NAME = "dig"


def build_application(argv: list[str] | None = None) -> QApplication:
    """Create the QApplication with the identity KDE needs to group the window."""
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Dig")
    app.setApplicationDisplayName("Dig")
    app.setOrganizationName("Kamsiob")
    app.setApplicationVersion(__version__)
    # Ties the Wayland window to the .desktop launcher so Plasma shows the
    # right icon and groups them together.
    QGuiApplication.setDesktopFileName(DESKTOP_FILE_NAME)
    register_fonts()
    return app


def main(argv: list[str] | None = None) -> int:
    app = build_application(argv)

    store = Store()
    try:
        store.open()
    except SchemaTooNewError as too_new:
        QMessageBox.critical(None, "Dig", str(too_new))
        return 1

    mode = store.get_setting(APPEARANCE_KEY, SYSTEM_MODE)
    theme = ThemeManager(mode)
    theme.apply()

    window = MainWindow(store, theme)
    window.show()

    if store.recovery_notice:
        window.show_notice(store.recovery_notice)

    exit_code = app.exec()
    store.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
