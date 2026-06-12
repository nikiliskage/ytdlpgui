"""Advanced formats table inside a height-animated container.

A chevron text-button toggles the container open/closed (max-height animation).
The table is a ``QTableWidget`` (ID / Ext / Resolution / FPS / Codec / Size).
Selecting a row clears chip selection (handled by the parent) and vice versa.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleFactory,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app import icons
from app.core import contracts as c

_HEADERS = ["ID", "Ext", "Resolution", "FPS", "Codec", "Size"]


class _NoFocusDelegate(QStyledItemDelegate):
    """Strip the per-cell focus state so no focus rectangle is painted."""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        option.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, option, index)


def _fmt_size(filesize: int | None) -> str:
    if filesize is None:
        return "—"
    mb = filesize / (1024 * 1024)
    return f"{mb:.1f} MB"


def _fmt_fps(fps: float | None) -> str:
    if fps is None:
        return "—"
    return str(int(fps)) if fps == int(fps) else str(fps)


class FormatTable(QWidget):
    """Collapsible advanced-formats section."""

    format_selected = Signal(str)  # emits the chosen format_id
    toggled_open = Signal(bool)

    def __init__(self, reduced_motion: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reduced_motion = reduced_motion
        self._open = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toggle_btn = QPushButton("  Advanced formats")
        self.toggle_btn.setObjectName("AdvToggle")
        self.toggle_btn.setIcon(icons.icon("chev_right", "#9a9aa6"))
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setFlat(True)
        self.toggle_btn.clicked.connect(self.toggle)
        layout.addWidget(self.toggle_btn)

        self._container = QWidget()
        self._container.setMaximumHeight(0)
        cont_layout = QVBoxLayout(self._container)
        cont_layout.setContentsMargins(0, 10, 0, 0)

        self.table = QTableWidget(0, len(_HEADERS))
        self.table.setObjectName("FormatTable")
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        # The native Windows 11 style paints a pink/accent selection bar at the
        # view level (ignores QSS/delegate); Fusion respects our QSS selection.
        fusion = QStyleFactory.create("Fusion")
        if fusion is not None:
            self._fusion_style = fusion  # keep a reference alive (Qt doesn't own it)
            self.table.setStyle(fusion)
        # No per-cell focus rectangle/editor box — only the purple row selection.
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setItemDelegate(_NoFocusDelegate(self.table))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setFixedHeight(200)
        self.table.itemSelectionChanged.connect(self._on_selection)
        cont_layout.addWidget(self.table)
        layout.addWidget(self._container)

        self._anim = QPropertyAnimation(self._container, b"maximumHeight", self)
        self._anim.setDuration(1 if reduced_motion else 320)

    # -- data -----------------------------------------------------------------
    def set_formats(self, formats: list[c.FormatInfo]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(formats))
        for row, f in enumerate(formats):
            codec = f.note or f.vcodec or f.acodec or ""
            values = [
                f.format_id,
                f.ext,
                f.resolution,
                _fmt_fps(f.fps),
                codec,
                _fmt_size(f.filesize),
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, f.format_id)
                self.table.setItem(row, col, item)
        self.table.clearSelection()
        self.table.blockSignals(False)

    # -- open / close ---------------------------------------------------------
    def is_open(self) -> bool:
        return self._open

    def toggle(self) -> None:
        self.set_open(not self._open)

    def set_open(self, is_open: bool) -> None:
        self._open = is_open
        self.toggle_btn.setIcon(icons.icon("chev_down" if is_open else "chev_right", "#9a9aa6"))
        self._anim.stop()
        self._anim.setStartValue(self._container.maximumHeight())
        self._anim.setEndValue(220 if is_open else 0)
        self._anim.start()
        self.toggled_open.emit(is_open)

    def set_visible_section(self, visible: bool) -> None:
        """Hide the entire advanced section (subtitle mode hides it)."""
        self.setVisible(visible)
        if not visible and self._open:
            self.set_open(False)

    # -- selection ------------------------------------------------------------
    def _on_selection(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        id_item = self.table.item(row, 0)
        if id_item is not None:
            fmt = id_item.data(Qt.ItemDataRole.UserRole)
            if fmt:
                self.format_selected.emit(str(fmt))

    def clear_selection(self) -> None:
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.blockSignals(False)
