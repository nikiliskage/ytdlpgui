"""Mono input + Browse button + a status line (green ✓ / red ⚠)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PathField(QWidget):
    """Binary/path input with Browse and an optional status line below."""

    path_changed = Signal(str)

    def __init__(
        self,
        value: str = "",
        show_status: bool = True,
        pick_dir: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._pick_dir = pick_dir
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.input = QLineEdit(value)
        self.input.setProperty("class", "sp-input sp-input-mono")
        self.input.textChanged.connect(self.path_changed.emit)
        row.addWidget(self.input, 1)
        self.browse = QPushButton("Browse…")
        self.browse.setProperty("class", "sp-browse")
        self.browse.clicked.connect(self._on_browse)
        row.addWidget(self.browse)
        layout.addLayout(row)

        self.status = QLabel("")
        self.status.setVisible(show_status)
        layout.addWidget(self.status)

    def _on_browse(self) -> None:
        if self._pick_dir:
            path = QFileDialog.getExistingDirectory(self, "Select folder", self.input.text())
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select file", self.input.text())
        if path:
            self.input.setText(path)

    def text(self) -> str:
        return self.input.text()

    def set_status(self, message: str, ok: bool) -> None:
        self.status.setText(message)
        self.status.setProperty("class", "sp-status-ok" if ok else "sp-status-bad")
        style = self.status.style()
        style.unpolish(self.status)
        style.polish(self.status)
