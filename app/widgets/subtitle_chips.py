"""Subtitle-language chips for the media card (single-select).

Built from the languages the user configured in Settings. After a fetch the
chips that the video actually offers (manual or auto captions) stay selectable;
the rest are disabled (greyed) so it's clear they can't be downloaded. Only one
language can be active at a time.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from app.ui_state import lang_label


class _SubChip(QPushButton):
    """A checkable chip showing a language label with a faint code suffix."""

    def __init__(self, code: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.code = code
        self.setProperty("class", "chip")
        self.setCheckable(True)
        self.setText(f"{lang_label(code)}  {code}")


class SubtitleChips(QWidget):
    """Row of subtitle-language chips; single-select, emits the chosen code."""

    changed = Signal(list)  # emits list[str]: [] or a single language code

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._chips: dict[str, _SubChip] = {}
        self._available: set[str] = set()
        self._selected: str | None = None

    def set_langs(self, configured: list[str], available: set[str]) -> None:
        """Rebuild chips for *configured* langs; enable those in *available*.

        Pre-selects the first available language (in configured order) so the
        common case needs no extra clicks.
        """
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self._chips.clear()
        self._available = set(available)
        self._selected = next((code for code in configured if code in self._available), None)

        for code in configured:
            chip = _SubChip(code)
            usable = code in self._available
            chip.setEnabled(usable)
            chip.setCursor(
                Qt.CursorShape.PointingHandCursor if usable else Qt.CursorShape.ArrowCursor
            )
            if not usable:
                chip.setToolTip("No subtitles in this language for this video.")
            chip.clicked.connect(lambda _=False, c=code: self._select(c))
            self._layout.addWidget(chip)
            self._chips[code] = chip

        self._layout.addStretch(1)
        self._refresh()
        self.changed.emit(self.selected())

    def selected(self) -> list[str]:
        return [self._selected] if self._selected else []

    def has_unavailable(self) -> bool:
        """True if any configured language is missing for the current video."""
        return any(code not in self._available for code in self._chips)

    def _select(self, code: str) -> None:
        if code not in self._available:
            return
        # Single-select: clicking the active chip clears it, else it becomes the one.
        self._selected = None if code == self._selected else code
        self._refresh()
        self.changed.emit(self.selected())

    def _refresh(self) -> None:
        for code, chip in self._chips.items():
            on = code == self._selected
            chip.setChecked(on)
            chip.setProperty("selected", "true" if on else "false")
            style = chip.style()
            style.unpolish(chip)
            style.polish(chip)
