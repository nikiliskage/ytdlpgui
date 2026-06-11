"""Circular progress ring drawn with QPainter (dock signature element).

The value is animated via ``QVariantAnimation`` (no per-frame QSS). The
color-state decision is extracted into the pure :func:`ring_color` helper so it
can be unit-tested without a widget. ``paintEvent`` tolerates ``percent=None``
(indeterminate) and the 0/100 boundaries without raising.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.core import contracts as c

# Token colors.
_ACCENT = "#a855f7"
_SUCCESS = "#3ecf8e"
_ERROR = "#ff5470"
_TRACK = "#34343f"
_TEXT = "#e8e8ee"


def ring_color(state: c.JobState) -> str:
    """Pure helper: ring fill color for a job state (color-blind: also % text).

    accent while active/queued → green when done → red on error/cancel.
    """
    if state == c.JobState.COMPLETED:
        return _SUCCESS
    if state in (c.JobState.FAILED, c.JobState.CANCELED):
        return _ERROR
    return _ACCENT


class ProgressRing(QWidget):
    """40x40 ring with a 3px stroke, round caps, value starting at 12 o'clock."""

    def __init__(
        self,
        diameter: int = 40,
        stroke: int = 3,
        reduced_motion: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._diameter = diameter
        self._stroke = stroke
        self._reduced_motion = reduced_motion
        self._percent: float | None = 0.0
        self._display: float = 0.0  # animated value actually drawn
        self._state: c.JobState = c.JobState.QUEUED
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(1 if reduced_motion else 450)
        self._anim.valueChanged.connect(self._on_anim)
        self.setFixedSize(diameter, diameter)

    # -- animated draw property ----------------------------------------------
    def _get_display(self) -> float:
        return self._display

    def _set_display(self, value: float) -> None:
        self._display = value
        self.update()

    display = Property(float, _get_display, _set_display)

    def _on_anim(self, value: object) -> None:
        self._set_display(float(value))  # type: ignore[arg-type]

    # -- public API -----------------------------------------------------------
    def set_state(self, state: c.JobState) -> None:
        self._state = state
        self.update()

    def state(self) -> c.JobState:
        return self._state

    def set_percent(self, percent: float | None) -> None:
        """Set target percent (0-100) or None for indeterminate."""
        self._percent = percent
        target = 0.0 if percent is None else max(0.0, min(100.0, percent))
        self._anim.stop()
        self._anim.setStartValue(self._display)
        self._anim.setEndValue(target)
        self._anim.start()

    def percent(self) -> float | None:
        return self._percent

    # -- painting -------------------------------------------------------------
    def paintEvent(self, event: object) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        half = self._stroke / 2.0
        rect = QRectF(half, half, self._diameter - self._stroke, self._diameter - self._stroke)

        # track
        track_pen = QPen(QColor(_TRACK), self._stroke)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # fill — start at 12 o'clock (90°), clockwise. None → nothing drawn.
        if self._percent is not None:
            fill_pen = QPen(QColor(ring_color(self._state)), self._stroke)
            fill_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(fill_pen)
            span = int(-self._display / 100.0 * 360 * 16)
            painter.drawArc(rect, 90 * 16, span)

        # center label: % text (or check/cross for terminal states)
        painter.setPen(QColor(ring_color(self._state) if self._state.is_terminal else _TEXT))
        font = QFont()
        font.setPixelSize(int(self._diameter * 0.24))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        if self._state == c.JobState.COMPLETED:
            label = "OK"
        elif self._state in (c.JobState.FAILED, c.JobState.CANCELED):
            label = "X"
        elif self._percent is None:
            label = "..."
        else:
            label = f"{int(round(self._percent))}%"
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, label)
        painter.end()
