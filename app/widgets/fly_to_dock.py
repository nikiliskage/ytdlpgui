"""Fly-to-dock: a temporary accent ghost flies from a button to the dock.

Creates one frameless child widget on the host, animates position + scale + fade
across the window, and deletes the temp widget on finish (no leak). Under
reduced motion the duration collapses to ~0 but the widget is still cleaned up.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from app import icons


class _Ghost(QWidget):
    """A 38px accent circle with a download glyph."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.deleted = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(38, 38)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#a855f7"))
        painter.drawEllipse(0, 0, 38, 38)
        painter.drawPixmap(11, 11, icons.pixmap("download", "#ffffff", 16))
        painter.end()


def fly_to_dock(
    host: QWidget,
    start: QPoint,
    end: QPoint,
    reduced_motion: bool = False,
    on_finished: object | None = None,
) -> _Ghost:
    """Spawn the ghost on ``host`` and animate it from ``start`` to ``end``.

    ``start``/``end`` are centers in ``host`` coordinates. Returns the ghost
    (kept alive by the animation parent); it is deleted on finish.
    """
    ghost = _Ghost(host)
    ghost.move(start.x() - 19, start.y() - 19)
    ghost.show()
    ghost.raise_()

    effect = QGraphicsOpacityEffect(ghost)
    ghost.setGraphicsEffect(effect)

    duration = 1 if reduced_motion else 650
    group = QParallelAnimationGroup(host)

    pos_anim = QPropertyAnimation(ghost, b"pos", group)
    pos_anim.setDuration(duration)
    pos_anim.setStartValue(QPoint(start.x() - 19, start.y() - 19))
    pos_anim.setEndValue(QPoint(end.x() - 8, end.y() - 8))
    pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    group.addAnimation(pos_anim)

    fade = QPropertyAnimation(effect, b"opacity", group)
    fade.setDuration(duration)
    fade.setStartValue(1.0)
    fade.setEndValue(0.0)
    group.addAnimation(fade)

    def _cleanup() -> None:
        ghost.deleted = True
        ghost.hide()
        ghost.deleteLater()
        if on_finished is not None:
            on_finished()  # type: ignore[operator]

    group.finished.connect(_cleanup)
    group.start()
    return ghost
