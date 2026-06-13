"""Reusable inline tinted band (error / cookie / banner share this recipe).

Errors are *never* modal — always an inline band: 1px tinted border + ~8% tinted
bg + icon + bold lead. This widget is the error-band variant under the omni-bar
with a Retry button.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from app import icons


class ErrorBand(QWidget):
    """Inline error band with bold lead, server message, and Retry."""

    retry = Signal()
    action = Signal()  # optional context action (e.g. "Enable cookies")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ErrorBand")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(10)

        self._icon = QLabel()
        self._icon.setPixmap(icons.pixmap("warn", "#ff5470", 16))
        layout.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)

        self._msg = QLabel()
        self._msg.setWordWrap(True)
        self._msg.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._msg, 1)

        # Gap so the buttons sit a little to the right of the message.
        layout.addSpacing(16)

        # Optional context action (e.g. "Enable cookies"); hidden unless set.
        self._action = QPushButton()
        self._action.clicked.connect(self.action.emit)
        self._action.setVisible(False)
        layout.addWidget(self._action)

        self._retry = QPushButton("Retry")
        self._retry.clicked.connect(self.retry.emit)
        layout.addWidget(self._retry)

    def set_message(self, message: str, lead: str = "Couldn't fetch this URL.") -> None:
        """Set the bold lead on top with the specific reason on the line below."""
        self._msg.setText(
            f"<b style='color:#ff5470'>{lead}</b><br><span style='color:#f3a7b4'>{message}</span>"
        )

    def set_action(self, label: str) -> None:
        """Show a context action button with *label*, or hide it when empty."""
        if label:
            self._action.setText(label)
            self._action.setVisible(True)
        else:
            self._action.setVisible(False)
