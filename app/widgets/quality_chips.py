"""Single-select quality chips; chip set + suffix depend on the mode."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from app.core import contracts as c
from app.ui_state import CHIPS_BY_MODE


class _Chip(QPushButton):
    """A pill chip with a label and faint suffix."""

    def __init__(self, chip_id: str, label: str, sub: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.chip_id = chip_id
        self.setProperty("class", "chip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setText(f"{label}  {sub}")


class QualityChips(QWidget):
    """Row of toggle chips; emits the selected chip id (single-select)."""

    chip_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._chips: list[_Chip] = []
        self._selected: str | None = None

    def set_mode(self, mode: c.DownloadMode) -> None:
        """Rebuild chips for the mode and select the first."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                w.deleteLater()
        self._chips.clear()
        for chip_id, label, sub in CHIPS_BY_MODE[mode]:
            chip = _Chip(chip_id, label, sub)
            chip.clicked.connect(lambda _=False, cid=chip_id: self.select(cid))
            self._layout.addWidget(chip)
            self._chips.append(chip)
        self._layout.addStretch(1)
        first = CHIPS_BY_MODE[mode][0][0]
        self.select(first, emit=False)

    def select(self, chip_id: str, emit: bool = True) -> None:
        self._selected = chip_id
        for chip in self._chips:
            on = chip.chip_id == chip_id
            chip.setChecked(on)
            chip.setProperty("selected", "true" if on else "false")
            style = chip.style()
            style.unpolish(chip)
            style.polish(chip)
        if emit:
            self.chip_selected.emit(chip_id)

    def selected(self) -> str | None:
        return self._selected

    def clear_selection(self) -> None:
        """Deselect all chips (used when a format row is picked instead)."""
        self._selected = None
        for chip in self._chips:
            chip.setChecked(False)
            chip.setProperty("selected", "false")
            style = chip.style()
            style.unpolish(chip)
            style.polish(chip)
