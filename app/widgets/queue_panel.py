"""Queue panel that expands upward from the dock (overlay; never reflows)."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import icons
from app.core import contracts as c

_STATUS_WORD = {
    c.JobState.RUNNING: ("downloading", "#f0c75a"),
    c.JobState.COMPLETED: ("done", "#3ecf8e"),
    c.JobState.FAILED: ("failed", "#ff5470"),
    c.JobState.CANCELED: ("canceled", "#ff5470"),
    c.JobState.QUEUED: ("queued", "#6b6b78"),
}


class QueueRow(QWidget):
    """A single queue row: info | progress bar | actions."""

    cancel = Signal(str)
    retry = Signal(str)
    open_folder = Signal(str)
    remove = Signal(str)

    def __init__(self, job_id: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.job_id = job_id
        self.setProperty("class", "q-row")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(16)

        info = QVBoxLayout()
        info.setSpacing(5)
        self._title = QLabel(title)
        self._title.setStyleSheet("font-size:13px;font-weight:500;")
        self._meta = QLabel("queued")
        self._meta.setStyleSheet("font-size:11px;color:#6b6b78;")
        info.addWidget(self._title)
        info.addWidget(self._meta)
        layout.addLayout(info, 1)

        self._bar = QProgressBar()
        self._bar.setTextVisible(False)
        self._bar.setFixedSize(150, 5)
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        layout.addWidget(self._bar)

        actions = QHBoxLayout()
        actions.setSpacing(4)
        self._cancel = self._act("close", lambda: self.cancel.emit(job_id))
        self._retry = self._act("retry", lambda: self.retry.emit(job_id))
        self._folder = self._act("folder", lambda: self.open_folder.emit(job_id))
        self._remove = self._act("trash", lambda: self.remove.emit(job_id))
        for a in (self._cancel, self._retry, self._folder, self._remove):
            actions.addWidget(a)
        layout.addLayout(actions)
        self.set_state(c.JobState.QUEUED)

    def _act(self, glyph: str, slot: object) -> QPushButton:
        btn = QPushButton()
        btn.setProperty("class", "q-act")
        btn.setIcon(icons.icon(glyph, "#6b6b78"))
        btn.setFixedSize(28, 28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        return btn

    def update_progress(self, progress: c.Progress) -> None:
        pct = progress.percent
        if pct is not None:
            self._bar.setValue(int(pct))
        bits = []
        if progress.speed:
            bits.append(f"{progress.speed / 1024 / 1024:.1f} MB/s")
        if progress.eta is not None:
            bits.append(f"ETA {progress.eta // 60:02d}:{progress.eta % 60:02d}")
        if bits:
            word, color = _STATUS_WORD[c.JobState.RUNNING]
            self._meta.setText(
                f"<span style='color:{color};font-weight:600'>{word}</span> · " + " · ".join(bits)
            )

    def set_state(self, state: c.JobState, message: str = "") -> None:
        word, color = _STATUS_WORD[state]
        text = f"<span style='color:{color};font-weight:600'>{word}</span>"
        if message:
            text += f" · {message}"
        self._meta.setText(text)
        chunk = {
            c.JobState.COMPLETED: "#3ecf8e",
            c.JobState.FAILED: "#ff5470",
            c.JobState.CANCELED: "#ff5470",
        }.get(state, "#a855f7")
        self._bar.setStyleSheet(
            "QProgressBar{background:#34343f;border:none;border-radius:3px;}"
            f"QProgressBar::chunk{{background:{chunk};border-radius:3px;}}"
        )
        if state == c.JobState.COMPLETED:
            self._bar.setValue(100)
        self._cancel.setVisible(state == c.JobState.RUNNING)
        self._retry.setVisible(state == c.JobState.FAILED)
        self._folder.setVisible(state == c.JobState.COMPLETED)


class QueuePanel(QWidget):
    """Overlay panel anchored to the dock top; slides up + fades."""

    clear_completed = Signal()

    def __init__(self, reduced_motion: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("QueuePanel")
        self._reduced_motion = reduced_motion
        self._open = False
        self._rows: dict[str, QueueRow] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        head = QHBoxLayout()
        head.setContentsMargins(20, 14, 20, 10)
        head.setSpacing(10)
        title = QLabel("Download queue")
        title.setObjectName("QpTitle")
        head.addWidget(title)
        self._count = QLabel("0 items")
        self._count.setObjectName("QpCount")
        head.addWidget(self._count)
        head.addStretch(1)
        clear = QPushButton("Clear completed")
        clear.setObjectName("QpClear")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.clicked.connect(self.clear_completed.emit)
        head.addWidget(clear)
        layout.addLayout(head)

        self._list = QVBoxLayout()
        self._list.setContentsMargins(12, 0, 12, 12)
        self._list.setSpacing(2)
        layout.addLayout(self._list)
        layout.addStretch(1)

        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._opacity_anim.setDuration(1 if reduced_motion else 300)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def add_row(self, job_id: str, title: str) -> QueueRow:
        row = QueueRow(job_id, title)
        self._list.addWidget(row)
        self._rows[job_id] = row
        self._update_count()
        return row

    def remove_row(self, job_id: str) -> None:
        row = self._rows.pop(job_id, None)
        if row is not None:
            row.setParent(None)
            row.deleteLater()
        self._update_count()

    def row(self, job_id: str) -> QueueRow | None:
        return self._rows.get(job_id)

    def rows(self) -> dict[str, QueueRow]:
        return self._rows

    def _update_count(self) -> None:
        self._count.setText(f"{len(self._rows)} items")

    def is_open(self) -> bool:
        return self._open

    def set_open(self, is_open: bool) -> None:
        self._open = is_open
        self.setVisible(is_open)
