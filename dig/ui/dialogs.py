"""Dialogs that match the rest of Dig: square corners, plain words, no apology."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from dig.theme.tokens import Palette
from dig.ui.widgets import TextButton


class ConfirmDialog(QDialog):
    """Ask once, in plain words, before something cannot be undone."""

    def __init__(
        self,
        palette: Palette,
        question: str,
        confirm_label: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Dig")
        self.setObjectName("ConfirmDialog")
        self.setMinimumWidth(400)

        column = QVBoxLayout(self)
        column.setContentsMargins(26, 24, 26, 22)
        column.setSpacing(20)

        message = QLabel(question)
        message.setObjectName("ConfirmText")
        message.setWordWrap(True)
        column.addWidget(message)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(12)
        actions.addStretch(1)

        self.cancel_button = TextButton("Keep it", "GhostButton")
        self.cancel_button.clicked.connect(self.reject)
        actions.addWidget(self.cancel_button)

        self.confirm_button = TextButton(confirm_label, "DangerButton")
        self.confirm_button.clicked.connect(self.accept)
        actions.addWidget(self.confirm_button)

        column.addLayout(actions)

        # Cancel is the safe default: Enter must not destroy anything.
        self.cancel_button.setDefault(True)
        self.cancel_button.setFocus()

    @staticmethod
    def ask(
        parent: QWidget | None,
        palette: Palette,
        question: str,
        confirm_label: str = "Delete",
    ) -> bool:
        dialog = ConfirmDialog(palette, question, confirm_label, parent)
        return dialog.exec() == QDialog.DialogCode.Accepted
