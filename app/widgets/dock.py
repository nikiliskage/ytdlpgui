"""Persistent bottom Download Dock (86px) with circular progress rings.

Each item carries a ProgressRing (with % text — color-blind safety), a
truncated title, and a status sub-line. Rings are the default; a bar variant is
available via ``dock_style``. New items pop in. Clicking an item or the chevron
opens the queue panel.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import icons
from app.core import contracts as c
from app.widgets.progress_ring import ProgressRing

_STATUS_CLASS = {
    c.JobState.RUNNING: "s-downloading",
    c.JobState.COMPLETED: "s-done",
    c.JobState.FAILED: "s-error",
    c.JobState.CANCELED: "s-error",
    c.JobState.QUEUED: "s-queued",
}
_STATUS_COLOR = {
    "s-downloading": "#f0c75a",
    "s-done": "#3ecf8e",
    "s-error": "#ff5470",
    "s-queued": "#6b6b78",
}


def _truncate(text: str, length: int = 13) -> str:
    return text if len(text) <= length else text[: length - 1] + "…"


class DockItem(QWidget):
    """A single ring-style dock entry (vertical mini-button)."""

    clicked = Signal(str)

    def __init__(
        self, job_id: str, title: str, reduced_motion: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.job_id = job_id
        self._title = title
        self.setProperty("class", "dock-item")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(86)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 5)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.ring = ProgressRing(reduced_motion=reduced_motion)
        layout.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)

        self._label = QLabel(_truncate(title))
        self._label.setStyleSheet("font-size:10px;color:#9a9aa6;")
        layout.addWidget(self._label, 0, Qt.AlignmentFlag.AlignHCenter)

        self._sub = QLabel("queued")
        self._sub.setStyleSheet("font-size:9px;color:#6b6b78;")
        layout.addWidget(self._sub, 0, Qt.AlignmentFlag.AlignHCenter)

        # pop-in
        self._anim = QPropertyAnimation(self, b"maximumWidth", self)
        self._anim.setDuration(1 if reduced_motion else 400)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._anim.setStartValue(0)
        self._anim.setEndValue(110)
        self._anim.start()

    def mousePressEvent(self, event: object) -> None:  # noqa: N802
        self.clicked.emit(self.job_id)

    def update_progress(self, progress: c.Progress) -> None:
        self.ring.set_percent(progress.percent)
        if progress.speed:
            self._sub.setText(f"{progress.speed / 1024 / 1024:.1f} MB/s")
            self._set_sub_class("s-downloading")

    def set_state(self, state: c.JobState) -> None:
        self.ring.set_state(state)
        cls = _STATUS_CLASS.get(state, "s-queued")
        words = {
            "s-downloading": "downloading",
            "s-done": "done",
            "s-error": "failed",
            "s-queued": "queued",
        }
        self._sub.setText(words[cls])
        self._set_sub_class(cls)

    def _set_sub_class(self, cls: str) -> None:
        self._sub.setStyleSheet(f"font-size:9px;color:{_STATUS_COLOR[cls]};")


class Dock(QWidget):
    """The 86px dock bar with items and an expand chevron."""

    item_clicked = Signal(str)
    expand_clicked = Signal()

    def __init__(self, reduced_motion: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Dock")
        self.setFixedHeight(86)
        self._reduced_motion = reduced_motion
        self._items: dict[str, DockItem] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(6)

        self._empty = QLabel("Queue is empty — fetched media lands here.")
        self._empty.setObjectName("DockEmpty")
        layout.addWidget(self._empty)

        self._items_layout = QHBoxLayout()
        self._items_layout.setSpacing(4)
        layout.addLayout(self._items_layout, 1)
        layout.addStretch(1)

        self._stat = QLabel("0 active · 0 done")
        self._stat.setObjectName("DockStat")
        layout.addWidget(self._stat)

        self.expand_btn = QPushButton()
        self.expand_btn.setObjectName("DockExpand")
        self.expand_btn.setIcon(icons.icon("chev_up", "#9a9aa6"))
        self.expand_btn.setFixedSize(34, 34)
        self.expand_btn.setEnabled(False)
        self.expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.expand_btn.clicked.connect(self.expand_clicked.emit)
        layout.addWidget(self.expand_btn)

    def add_item(self, job_id: str, title: str) -> DockItem:
        self._empty.setVisible(False)
        item = DockItem(job_id, title, self._reduced_motion)
        item.clicked.connect(self.item_clicked.emit)
        self._items_layout.addWidget(item)
        self._items[job_id] = item
        self.expand_btn.setEnabled(True)
        self._update_summary()
        return item

    def remove_item(self, job_id: str) -> None:
        item = self._items.pop(job_id, None)
        if item is not None:
            item.setParent(None)
            item.deleteLater()
        if not self._items:
            self._empty.setVisible(True)
            self.expand_btn.setEnabled(False)
        self._update_summary()

    def item(self, job_id: str) -> DockItem | None:
        return self._items.get(job_id)

    def update_progress(self, job_id: str, progress: c.Progress) -> None:
        item = self._items.get(job_id)
        if item is not None:
            item.update_progress(progress)

    def set_state(self, job_id: str, state: c.JobState) -> None:
        item = self._items.get(job_id)
        if item is not None:
            item.set_state(state)
        self._update_summary()

    def _update_summary(self) -> None:
        done = sum(1 for it in self._items.values() if it.ring.state() == c.JobState.COMPLETED)
        active = len(self._items) - done
        self._stat.setText(f"{active} active · {done} done")

    def queue_btn_geometry_center(self) -> tuple[int, int]:
        """Center of the expand button (fly-to-dock landing point)."""
        rect = self.expand_btn.geometry()
        pt = self.expand_btn.mapTo(self.window(), rect.center() - rect.topLeft())
        return pt.x(), pt.y()
