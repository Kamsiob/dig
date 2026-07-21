"""The About dialog: who made this, where to find more, and what it costs.

Nothing is sold here. The only money link is a tip jar, and it opens in a
browser like every other link.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from dig import __version__
from dig.theme.tokens import Palette
from dig.ui.widgets import TextButton, Wordmark

TAGLINE = "A place to bury ideas and dig them back up."

LINKS: tuple[tuple[str, str, str], ...] = (
    ("YouTube", "Kamsiob on Linux", "https://youtube.com/@kamsiob"),
    ("GitHub", "kamsiob", "https://github.com/kamsiob"),
    ("Website", "kamsiob.com", "https://kamsiob.com"),
    ("Buy Me a Coffee", "", "https://buymeacoffee.com/kamsiob"),
    ("Telegram", "Kamsiob Lab", "https://t.me/+g5LKm9rUnNcxMjk5"),
    ("Feedback", "hello@kamsiob.com", "mailto:hello@kamsiob.com"),
)

LICENCE_LINE = "Free and open source · AGPLv3"
PRIVACY_LINE = "Everything stays on your machine."


def open_link(url: str) -> bool:
    """Hand a link to the desktop. Dig never opens anything itself."""
    return QDesktopServices.openUrl(QUrl(url))


class AboutDialog(QDialog):
    """Small, quiet, and entirely made of links out."""

    def __init__(self, palette: Palette, parent: QWidget | None = None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("About Dig")
        self.setObjectName("AboutDialog")
        self.setFixedWidth(440)

        column = QVBoxLayout(self)
        column.setContentsMargins(28, 26, 28, 24)
        column.setSpacing(0)

        self.wordmark = Wordmark(palette, size=24)
        column.addWidget(self.wordmark)
        column.addSpacing(4)

        tagline = QLabel(TAGLINE)
        tagline.setObjectName("AboutTagline")
        tagline.setWordWrap(True)
        column.addWidget(tagline)
        column.addSpacing(18)

        self.link_buttons: list[TextButton] = []
        for name, detail, url in LINKS:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)

            button = TextButton(name, "AboutLink")
            button.setProperty("url", url)
            button.clicked.connect(lambda _c=False, u=url: open_link(u))
            row.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
            self.link_buttons.append(button)

            if detail:
                suffix = QLabel(f"· {detail}")
                suffix.setObjectName("AboutLinkDetail")
                row.addWidget(suffix, 0, Qt.AlignmentFlag.AlignVCenter)

            row.addStretch(1)
            column.addLayout(row)
            column.addSpacing(9)

        column.addSpacing(9)
        licence = QLabel(f"{LICENCE_LINE}\n{PRIVACY_LINE}")
        licence.setObjectName("AboutLicence")
        column.addWidget(licence)
        column.addSpacing(16)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addStretch(1)
        version = QLabel(f"v{__version__}")
        version.setObjectName("AboutLicence")
        actions.addWidget(version, 0, Qt.AlignmentFlag.AlignVCenter)
        close = TextButton("Close", "GhostButton")
        close.clicked.connect(self.accept)
        actions.addWidget(close)
        column.addLayout(actions)
