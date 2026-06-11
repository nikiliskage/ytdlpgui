"""Startup splash: frameless translucent QWidget (not QSplashScreen).

Runs a sequential checklist (Loading settings → Checking yt-dlp → Checking
ffmpeg). The real checks are *injected* as callables so the splash never imports
Stream A directly — each step callable returns an optional detail string (e.g. a
version) or raises on failure. Fade/scale via QPropertyAnimation; reduced motion
collapses durations.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app import icons

# A step = (label, callable→detail-or-None). Callable may raise to mark failure.
StepFn = Callable[[], str | None]
Step = tuple[str, StepFn]


class _LogoMark(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(58, 58)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, 58, 58)
        grad.setColorAt(0.0, QColor("#a855f7"))
        grad.setColorAt(1.0, QColor("#7437b8"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawRoundedRect(0, 0, 58, 58, 16, 16)
        painter.drawPixmap(20, 20, icons.pixmap("download", "#ffffff", 18))
        painter.end()


class _StepRow(QWidget):
    """One checklist row: status icon + label + (right) detail."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self._icon = QLabel("•")
        self._icon.setFixedWidth(16)
        layout.addWidget(self._icon)
        self._label = QLabel(label)
        self._label.setProperty("class", "splash-step")
        layout.addWidget(self._label, 1)
        self._detail = QLabel("")
        self._detail.setProperty("class", "splash-detail")
        layout.addWidget(self._detail)

    def set_running(self) -> None:
        self._icon.setText("…")
        self._label.setProperty("class", "splash-step-running")
        self._repolish()

    def set_done(self, detail: str | None) -> None:
        self._icon.setPixmap(icons.pixmap("check", "#3ecf8e", 14))
        self._label.setProperty("class", "splash-step-done")
        if detail:
            self._detail.setText(detail)
        self._repolish()

    def set_failed(self) -> None:
        self._icon.setPixmap(icons.pixmap("warn", "#ff5470", 14))
        self._repolish()

    def _repolish(self) -> None:
        for w in (self._label,):
            style = w.style()
            style.unpolish(w)
            style.polish(w)


class Splash(QWidget):
    """Frameless splash that runs injected startup checks then signals done."""

    finished = Signal()

    def __init__(
        self,
        steps: list[Step] | None = None,
        reduced_motion: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._reduced_motion = reduced_motion
        self._steps = steps or []
        self._rows: list[_StepRow] = []
        self._index = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QWidget()
        card.setObjectName("SplashCard")
        card.setFixedWidth(440)
        self._card = card
        outer.addWidget(card)

        col = QVBoxLayout(card)
        col.setContentsMargins(40, 44, 40, 24)
        col.setSpacing(0)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        col.addWidget(_LogoMark(), 0, Qt.AlignmentFlag.AlignHCenter)
        name = QLabel("yt-dlp <span style='color:#9a9aa6;font-weight:400'>GUI</span>")
        name.setObjectName("SplashName")
        name.setTextFormat(Qt.TextFormat.RichText)
        name.setContentsMargins(0, 18, 0, 0)
        col.addWidget(name, 0, Qt.AlignmentFlag.AlignHCenter)
        version = QLabel("version 0.3.0")
        version.setObjectName("SplashVersion")
        col.addWidget(version, 0, Qt.AlignmentFlag.AlignHCenter)

        steps_box = QWidget()
        steps_box.setMaximumWidth(280)
        self._steps_layout = QVBoxLayout(steps_box)
        self._steps_layout.setContentsMargins(0, 28, 0, 30)
        self._steps_layout.setSpacing(9)
        for label, _ in self._steps:
            row = _StepRow(label)
            self._rows.append(row)
            self._steps_layout.addWidget(row)
        col.addWidget(steps_box, 0, Qt.AlignmentFlag.AlignHCenter)

    # -- sequence -------------------------------------------------------------
    def run(self) -> None:
        """Start running the checklist. Safe to call after show()."""
        QTimer.singleShot(0, self._run_next)

    def _run_next(self) -> None:
        if self._index >= len(self._steps):
            self._leave()
            return
        row = self._rows[self._index]
        _, fn = self._steps[self._index]
        row.set_running()
        try:
            detail = fn()
            row.set_done(detail)
        except Exception:
            row.set_failed()
        self._index += 1
        delay = 1 if self._reduced_motion else 120
        QTimer.singleShot(delay, self._run_next)

    def _leave(self) -> None:
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(1 if self._reduced_motion else 350)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(self._on_left)
        self._leave_anim = anim  # keep ref
        anim.start()

    def _on_left(self) -> None:
        self.finished.emit()
        self.close()
