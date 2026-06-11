"""Fetching skeleton: thumb block + 3 text lines with a shimmer sweep."""

from __future__ import annotations

from PySide6.QtCore import Property, QPropertyAnimation, QRect, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget


class _ShimmerBlock(QWidget):
    """A surface-2 rounded block with a moving highlight sweep."""

    def __init__(self, reduced_motion: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._phase = -1.0
        self._anim = QPropertyAnimation(self, b"phase", self)
        self._anim.setStartValue(-1.0)
        self._anim.setEndValue(2.0)
        self._anim.setDuration(1 if reduced_motion else 1400)
        self._anim.setLoopCount(-1)
        self._anim.start()

    def _get_phase(self) -> float:
        return self._phase

    def _set_phase(self, value: float) -> None:
        self._phase = value
        self.update()

    phase = Property(float, _get_phase, _set_phase)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#2c2c36"))
        painter.drawRoundedRect(self.rect(), 6, 6)
        w = self.width()
        x = int(self._phase * w)
        grad = QLinearGradient(x - w * 0.3, 0, x + w * 0.3, 0)
        grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        grad.setColorAt(0.5, QColor(255, 255, 255, 13))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(grad)
        painter.drawRoundedRect(self.rect(), 6, 6)
        painter.end()


class Skeleton(QWidget):
    """Card-shaped placeholder shown while fetching."""

    def __init__(self, reduced_motion: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SkeletonCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)

        thumb = _ShimmerBlock(reduced_motion)
        thumb.setFixedSize(200, 112)
        layout.addWidget(thumb)

        lines = QVBoxLayout()
        lines.setSpacing(12)
        lines.setContentsMargins(0, 4, 0, 0)
        for ratio in (0.72, 0.38, 0.55):
            line = _ShimmerBlock(reduced_motion)
            line.setFixedHeight(14)
            line.setMaximumWidth(int(520 * ratio))
            lines.addWidget(line)
        lines.addStretch(1)
        layout.addLayout(lines, 1)

    def set_geometry_rect(self, rect: QRect) -> None:  # convenience for callers
        self.setGeometry(rect)
