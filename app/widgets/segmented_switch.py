"""Video / Audio / Subtitle segmented switch with an animated thumb."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtWidgets import QPushButton, QWidget

from app.core import contracts as c

_MODES: list[tuple[c.DownloadMode, str]] = [
    (c.DownloadMode.VIDEO, "Video"),
    (c.DownloadMode.AUDIO, "Audio"),
    (c.DownloadMode.SUBTITLE, "Subtitle"),
]


class SegmentedSwitch(QWidget):
    """Three flat buttons + a thumb animated behind the active one."""

    mode_changed = Signal(object)  # emits c.DownloadMode

    def __init__(self, reduced_motion: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Segmented")
        self._reduced_motion = reduced_motion
        self._mode = c.DownloadMode.VIDEO
        self._buttons: dict[c.DownloadMode, QPushButton] = {}
        self.setFixedHeight(34)

        self._thumb = QWidget(self)
        self._thumb.setObjectName("SegThumb")

        x = 3
        for mode, label in _MODES:
            btn = QPushButton(label, self)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFlat(True)
            btn.clicked.connect(lambda _=False, m=mode: self.set_mode(m))
            btn.adjustSize()
            w = btn.sizeHint().width() + 16
            btn.setGeometry(x, 3, w, 28)
            self._buttons[mode] = btn
            x += w + 2
        self.setFixedWidth(x + 1)

        self._anim = QPropertyAnimation(self._thumb, b"geometry", self)
        self._anim.setDuration(1 if reduced_motion else 220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._update_active(initial=True)

    def mode(self) -> c.DownloadMode:
        return self._mode

    def set_mode(self, mode: c.DownloadMode, emit: bool = True) -> None:
        if mode == self._mode:
            return
        self._mode = mode
        self._update_active()
        if emit:
            self.mode_changed.emit(mode)

    def _update_active(self, initial: bool = False) -> None:
        for mode, btn in self._buttons.items():
            btn.setProperty("active", "true" if mode == self._mode else "false")
            style = btn.style()
            style.unpolish(btn)
            style.polish(btn)
        active = self._buttons[self._mode]
        target = QRect(active.x(), 3, active.width(), 28)
        if initial:
            self._thumb.setGeometry(target)
        else:
            self._anim.stop()
            self._anim.setStartValue(self._thumb.geometry())
            self._anim.setEndValue(target)
            self._anim.start()
        self._thumb.lower()
