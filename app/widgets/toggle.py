"""38x22 toggle switch with an animated knob (settings panel)."""

from __future__ import annotations

from PySide6.QtCore import Property, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter
from PySide6.QtWidgets import QWidget

_TRACK_OFF = "#34343f"
_TRACK_ON = "#a855f7"
_KNOB_OFF = "#9a9aa6"
_KNOB_ON = "#ffffff"
_BORDER = "#34343e"


class Toggle(QWidget):
    """Checkable switch; off = surface-3 track, on = accent track."""

    toggled = Signal(bool)

    def __init__(
        self, checked: bool = False, reduced_motion: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._checked = checked
        self._pos = 16.0 if checked else 0.0
        self._reduced_motion = reduced_motion
        self.setFixedSize(38, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(1 if reduced_motion else 200)

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, value: float) -> None:
        self._pos = value
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def is_checked(self) -> bool:
        return self._checked

    def set_checked(self, checked: bool, animate: bool = True) -> None:
        if checked == self._checked:
            return
        self._checked = checked
        target = 16.0 if checked else 0.0
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._set_knob(target)
        self.toggled.emit(checked)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_checked(not self._checked)
        super().mousePressEvent(event)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QColor(_TRACK_ON if self._checked else _TRACK_OFF)
        painter.setPen(QColor(_TRACK_ON if self._checked else _BORDER))
        painter.setBrush(track)
        painter.drawRoundedRect(0, 0, 38, 22, 11, 11)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_KNOB_ON if self._checked else _KNOB_OFF))
        painter.drawEllipse(int(2 + self._pos), 3, 16, 16)
        painter.end()
