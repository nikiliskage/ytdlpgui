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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ErrorBand")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(10)

        self._icon = QLabel()
        self._icon.setPixmap(icons.pixmap("warn", "#ff5470", 16))
        layout.addWidget(self._icon)

        self._msg = QLabel()
        self._msg.setWordWrap(True)
        self._msg.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._msg, 1)

        self._retry = QPushButton("Retry")
        self._retry.clicked.connect(self.retry.emit)
        layout.addWidget(self._retry)

    def set_message(self, message: str) -> None:
        """Set the server message; lead is fixed bold copy per handoff."""
        self._msg.setText(
            "<b style='color:#ff5470'>Couldn't fetch this URL.</b> "
            f"<span style='color:#f3a7b4'>{message}</span>"
        )
