"""Persistent bottom Download Dock (86px) with circular progress rings.

Each item carries a ProgressRing (with % text — color-blind safety), a
truncated title, and a status sub-line. Rings are the default; a bar variant is
available via ``dock_style``. New items pop in. Clicking an item or the chevron
opens the queue panel; right-clicking an item offers Rename / Open folder.

Items live in a horizontally scrolling strip, so a long queue (e.g. a whole
playlist) never widens the dock — and with it the window — past the screen.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
    context_requested = Signal(str, QPoint)  # job_id, global position

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
        self.setToolTip(title)
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
        if getattr(event, "button", lambda: None)() == Qt.MouseButton.RightButton:
            return  # handled by contextMenuEvent
        self.clicked.emit(self.job_id)

    def contextMenuEvent(self, event: object) -> None:  # noqa: N802
        pos = getattr(event, "globalPos", lambda: self.mapToGlobal(self.rect().center()))()
        self.context_requested.emit(self.job_id, pos)

    def set_title(self, title: str) -> None:
        self._title = title
        self._label.setText(_truncate(title))
        self.setToolTip(title)

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


class _HScroll(QScrollArea):
    """Horizontal-only strip: no scrollbars (no room in 86px), wheel scrolls sideways."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DockScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Never let the item count dictate the dock's (and window's) minimum width.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta()
        step = delta.x() or delta.y()
        if step:
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - step)
            event.accept()
            return
        super().wheelEvent(event)


class Dock(QWidget):
    """The 86px dock bar with items and an expand chevron."""

    item_clicked = Signal(str)
    expand_clicked = Signal()
    rename_requested = Signal(str)
    open_folder_requested = Signal(str)

    def __init__(self, reduced_motion: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Dock")
        self.setFixedHeight(86)
        self._reduced_motion = reduced_motion
        self._items: dict[str, DockItem] = {}
        # Jobs whose finished file can be renamed (set by the main window).
        self._renamable: set[str] = set()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(6)

        self._empty = QLabel("Queue is empty — fetched media lands here.")
        self._empty.setObjectName("DockEmpty")
        layout.addWidget(self._empty)

        self.strip_scroll = _HScroll()
        strip = QWidget()
        strip.setObjectName("DockStrip")
        self._items_layout = QHBoxLayout(strip)
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(4)
        self._items_layout.addStretch(1)  # keep items left-aligned
        self.strip_scroll.setWidget(strip)
        layout.addWidget(self.strip_scroll, 1)

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
        item.context_requested.connect(self._show_menu)
        # Insert before the trailing stretch.
        self._items_layout.insertWidget(self._items_layout.count() - 1, item)
        self._items[job_id] = item
        self.expand_btn.setEnabled(True)
        self._update_summary()
        return item

    def remove_item(self, job_id: str) -> None:
        item = self._items.pop(job_id, None)
        self._renamable.discard(job_id)
        if item is not None:
            item.setParent(None)
            item.deleteLater()
        if not self._items:
            self._empty.setVisible(True)
            self.expand_btn.setEnabled(False)
        self._update_summary()

    def item(self, job_id: str) -> DockItem | None:
        return self._items.get(job_id)

    def job_ids(self, state: c.JobState | None = None) -> list[str]:
        """Ids of the dock's items, optionally only those in *state*."""
        return [
            job_id
            for job_id, item in self._items.items()
            if state is None or item.ring.state() == state
        ]

    def update_progress(self, job_id: str, progress: c.Progress) -> None:
        item = self._items.get(job_id)
        if item is not None:
            item.update_progress(progress)

    def set_state(self, job_id: str, state: c.JobState) -> None:
        item = self._items.get(job_id)
        if item is not None:
            item.set_state(state)
            if state == c.JobState.RUNNING:
                # Keep the download that just started in view on a long queue.
                self.strip_scroll.ensureWidgetVisible(item, 8, 0)
        self._update_summary()

    def set_title(self, job_id: str, title: str) -> None:
        item = self._items.get(job_id)
        if item is not None:
            item.set_title(title)

    def set_renamable(self, job_id: str, renamable: bool) -> None:
        if renamable:
            self._renamable.add(job_id)
        else:
            self._renamable.discard(job_id)

    def build_menu(self, job_id: str) -> QMenu:
        """Context menu for an item: Rename… / Open folder / Show in queue."""
        menu = QMenu(self)
        done = self._items[job_id].ring.state() == c.JobState.COMPLETED
        rename = menu.addAction("Rename…")
        rename.setEnabled(job_id in self._renamable)
        rename.triggered.connect(lambda: self.rename_requested.emit(job_id))
        folder = menu.addAction("Open folder")
        folder.setEnabled(done)
        folder.triggered.connect(lambda: self.open_folder_requested.emit(job_id))
        menu.addSeparator()
        show = menu.addAction("Show in queue")
        show.triggered.connect(lambda: self.item_clicked.emit(job_id))
        return menu

    def _show_menu(self, job_id: str, pos: QPoint) -> None:
        if job_id in self._items:
            self.build_menu(job_id).exec(pos)

    def _update_summary(self) -> None:
        done = sum(1 for it in self._items.values() if it.ring.state() == c.JobState.COMPLETED)
        active = len(self._items) - done
        self._stat.setText(f"{active} active · {done} done")

    def queue_btn_geometry_center(self) -> tuple[int, int]:
        """Center of the expand button (fly-to-dock landing point)."""
        rect = self.expand_btn.geometry()
        pt = self.expand_btn.mapTo(self.window(), rect.center() - rect.topLeft())
        return pt.x(), pt.y()
