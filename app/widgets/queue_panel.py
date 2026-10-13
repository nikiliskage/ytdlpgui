"""Queue panel that expands upward from the dock (overlay; never reflows)."""

from __future__ import annotations

import html
from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QFocusEvent, QFont, QFontMetrics, QKeyEvent, QResizeEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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


class _ElidedLabel(QLabel):
    """One-line label that shortens its text with "…" instead of growing.

    A plain QLabel's minimum width is its full text, so one long error message
    made a queue row wider than the panel and the list scrolled sideways. This
    one never asks for more width than it gets; the full text is its tooltip.
    An optional bold, colored *lead* (the status word) is never shortened.
    """

    def __init__(self, style: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(style)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(1)
        self._lead = ""
        self._lead_color = ""
        self._text = ""
        self._text_color = ""

    def set_parts(
        self, text: str, lead: str = "", lead_color: str = "", text_color: str = ""
    ) -> None:
        self._lead, self._lead_color = lead, lead_color
        self._text, self._text_color = text, text_color
        full = " · ".join(p for p in (lead, text) if p)
        self.setToolTip(full if len(full) > 40 else "")
        self._render()

    def plain_text(self) -> str:
        return " · ".join(p for p in (self._lead, self._text) if p)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(1, super().minimumSizeHint().height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._render()

    def _render(self) -> None:
        avail = max(0, self.width() - 2)
        html_parts: list[str] = []
        if self._lead:
            bold = QFont(self.font())
            bold.setWeight(QFont.Weight.DemiBold)
            avail -= QFontMetrics(bold).horizontalAdvance(self._lead + " · ")
            html_parts.append(
                f"<span style='color:{self._lead_color};font-weight:600'>"
                f"{html.escape(self._lead)}</span>"
            )
        if self._text:
            shown = self.fontMetrics().elidedText(self._text, Qt.TextElideMode.ElideRight, avail)
            body = html.escape(shown)
            if self._text_color:
                body = f"<span style='color:{self._text_color}'>{body}</span>"
            html_parts.append(body)
        self.setText(" · ".join(html_parts))


class _InlineEdit(QLineEdit):
    """Line edit for in-place renaming: Enter commits, Esc / focus loss cancels."""

    canceled = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.canceled.emit()
            event.accept()  # don't let Esc also close the queue panel
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        super().focusOutEvent(event)
        if self.isVisible():
            self.canceled.emit()


class QueueRow(QWidget):
    """A single queue row: info | progress bar | actions."""

    cancel = Signal(str)
    retry = Signal(str)
    open_folder = Signal(str)
    remove = Signal(str)
    rename = Signal(str, str)  # job_id, new file name (without extension)

    def __init__(self, job_id: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.job_id = job_id
        self.setProperty("class", "q-row")
        # File name (stem) of the finished download; None = not renamable.
        self._output_name: str | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(16)

        info = QVBoxLayout()
        info.setSpacing(5)
        self._title = _ElidedLabel("font-size:13px;font-weight:500;")
        self._title.set_parts(title)
        self._name_edit = _InlineEdit()
        self._name_edit.setObjectName("QRenameEdit")
        self._name_edit.setVisible(False)
        self._name_edit.returnPressed.connect(self._commit_rename)
        self._name_edit.canceled.connect(self._end_rename)
        self._meta = _ElidedLabel("font-size:11px;color:#6b6b78;")
        info.addWidget(self._title)
        info.addWidget(self._name_edit)
        info.addWidget(self._meta)
        layout.addLayout(info, 3)

        # The bar shares the row with the text (3:2) instead of sitting at a fixed
        # 150px on the far right, so there is no wide empty gap between them.
        self._bar = QProgressBar()
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(5)
        self._bar.setMinimumWidth(120)
        self._bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        layout.addWidget(self._bar, 2)

        # Fixed-width action area (room for the most buttons a row ever shows: 3),
        # so progress bars line up across rows whatever their state.
        actions_box = QWidget()
        actions_box.setFixedWidth(3 * 28 + 2 * 4)
        actions = QHBoxLayout(actions_box)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(4)
        actions.addStretch(1)
        self._cancel = self._act("close", lambda: self.cancel.emit(job_id))
        self._retry = self._act("retry", lambda: self.retry.emit(job_id))
        self._rename = self._act("edit", self.begin_rename)
        self._rename.setToolTip("Rename file")
        self._folder = self._act("folder", lambda: self.open_folder.emit(job_id))
        self._remove = self._act("trash", lambda: self.remove.emit(job_id))
        for a in (self._cancel, self._retry, self._rename, self._folder, self._remove):
            actions.addWidget(a)
        self._state = c.JobState.QUEUED
        layout.addWidget(actions_box)
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
            self._meta.set_parts(" · ".join(bits), lead=word, lead_color=color)

    def set_state(self, state: c.JobState, message: str = "", detail: str = "") -> None:
        word, color = _STATUS_WORD[state]
        self._meta.set_parts(message, lead=word, lead_color=color)
        # Full raw error on hover (the visible message may be clipped).
        self.setToolTip(detail)
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
        self._state = state
        self._cancel.setVisible(state == c.JobState.RUNNING)
        self._retry.setVisible(state == c.JobState.FAILED)
        self._folder.setVisible(state == c.JobState.COMPLETED)
        self._update_rename_btn()

    # -- rename ---------------------------------------------------------------
    def set_output_name(self, name: str | None) -> None:
        """File name (no extension) of the finished download; None hides Rename."""
        self._output_name = name
        self._update_rename_btn()

    def output_name(self) -> str | None:
        return self._output_name

    def _update_rename_btn(self) -> None:
        self._rename.setVisible(
            self._state == c.JobState.COMPLETED and self._output_name is not None
        )

    def begin_rename(self) -> None:
        """Swap the title for an inline editor pre-filled with the file name."""
        if self._output_name is None:
            return
        self._name_edit.setText(self._output_name)
        self._title.setVisible(False)
        self._name_edit.setVisible(True)
        self._name_edit.setFocus()
        self._name_edit.selectAll()

    def is_renaming(self) -> bool:
        return not self._name_edit.isHidden()

    def _commit_rename(self) -> None:
        new_name = self._name_edit.text().strip()
        self._end_rename()
        if new_name and new_name != self._output_name:
            self.rename.emit(self.job_id, new_name)

    def _end_rename(self) -> None:
        self._name_edit.setVisible(False)
        self._title.setVisible(True)

    def set_title(self, title: str) -> None:
        self._title.set_parts(title)

    def meta_text(self) -> str:
        """Plain status line (state word · message), unshortened."""
        return self._meta.plain_text()

    def show_note(self, message: str, error: bool = False) -> None:
        """Inline status after the state word (e.g. a rename result)."""
        word, color = _STATUS_WORD[self._state]
        note_color = "#ff5470" if error else "#9a9aa6"
        self._meta.set_parts(message, lead=word, lead_color=color, text_color=note_color)


class QueuePanel(QWidget):
    """Overlay panel anchored to the dock top; slides up + fades."""

    clear_completed = Signal()
    retry_failed = Signal()
    clear_failed = Signal()

    def __init__(self, reduced_motion: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("QueuePanel")
        # Required for the #QueuePanel QSS background to actually paint on a
        # plain QWidget (otherwise the overlay is transparent and shows through).
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._reduced_motion = reduced_motion
        self._open = False
        self._rows: dict[str, QueueRow] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._head = QWidget()
        head = QHBoxLayout(self._head)
        head.setContentsMargins(20, 14, 20, 10)
        head.setSpacing(10)
        title = QLabel("Download queue")
        title.setObjectName("QpTitle")
        head.addWidget(title)
        self._count = QLabel("0 items")
        self._count.setObjectName("QpCount")
        head.addWidget(self._count)
        head.addStretch(1)
        self.retry_failed_btn = self._head_btn("Retry failed", self.retry_failed.emit)
        self.clear_failed_btn = self._head_btn("Clear failed", self.clear_failed.emit)
        self.clear_completed_btn = self._head_btn("Clear completed", self.clear_completed.emit)
        for btn in (self.retry_failed_btn, self.clear_failed_btn, self.clear_completed_btn):
            head.addWidget(btn)
        layout.addWidget(self._head)

        # Rows live in a scroll area so a long queue scrolls instead of the
        # fixed-height overlay squashing rows on top of each other.
        scroll = QScrollArea()
        scroll.setObjectName("QpScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        list_host = QWidget()
        self._list = QVBoxLayout(list_host)
        self._list.setContentsMargins(12, 0, 12, 12)
        self._list.setSpacing(2)
        self._list.addStretch(1)  # keep rows top-aligned; new rows insert above
        scroll.setWidget(list_host)
        layout.addWidget(scroll, 1)

        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._opacity_anim.setDuration(1 if reduced_motion else 300)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @staticmethod
    def _head_btn(text: str, slot: Callable[[], object]) -> QPushButton:
        """Text-only header action (same look for every bulk action)."""
        btn = QPushButton(text)
        btn.setObjectName("QpClear")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        return btn

    def add_row(self, job_id: str, title: str) -> QueueRow:
        row = QueueRow(job_id, title)
        # Insert before the trailing stretch (last item) so rows stay top-aligned.
        self._list.insertWidget(self._list.count() - 1, row)
        self._rows[job_id] = row
        self._update_count()
        return row

    def content_height(self) -> int:
        """Natural height for header + all rows (before the overlay caps it).

        The main window uses this to size the bottom-sheet; the scroll area then
        handles any overflow beyond the cap.
        """
        head_h = self._head.sizeHint().height()
        rows_h = sum(r.sizeHint().height() + self._list.spacing() for r in self._rows.values())
        return head_h + rows_h + 14  # + list bottom margin

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
