"""Custom frameless title bar: logo + name + gear + min/max/close.

The whole bar drags the window. The gear toggles settings (accent when open).
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal, SignalInstance
from PySide6.QtGui import QColor, QLinearGradient, QMouseEvent, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from app import icons


class _LogoMark(QLabel):
    """22x22 rounded square logo with the purple gradient + download glyph."""

    def __init__(self, size: int = 22, glyph: int = 13, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self._glyph = glyph
        self.setFixedSize(size, size)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, self._size, self._size)
        grad.setColorAt(0.0, QColor("#a855f7"))
        grad.setColorAt(1.0, QColor("#7437b8"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        radius = max(4, self._size // 4)
        painter.drawRoundedRect(0, 0, self._size, self._size, radius, radius)
        off = (self._size - self._glyph) // 2
        painter.drawPixmap(off, off, icons.pixmap("download", "#ffffff", self._glyph))
        painter.end()


class TitleBar(QWidget):
    """46px title bar with window controls and a gear for settings."""

    gear_clicked = Signal()
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(46)
        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(_LogoMark())
        name = QLabel("yt-dlp <span style='color:#9a9aa6;font-weight:400'>GUI</span>")
        name.setObjectName("AppName")
        name.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(name)
        layout.addStretch(1)

        self.gear_btn = self._make_btn("gear", "TbGear", self.gear_clicked)
        layout.addWidget(self.gear_btn)

        divider = QWidget()
        divider.setFixedSize(1, 20)
        divider.setStyleSheet("background:#34343e;")
        layout.addWidget(divider)

        layout.addWidget(self._make_btn("min", "TbMin", self.minimize_clicked))
        layout.addWidget(self._make_btn("max", "TbMax", self.maximize_clicked))
        layout.addWidget(self._make_btn("close", "TbClose", self.close_clicked))

    def _make_btn(self, glyph: str, name: str, signal: SignalInstance) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName(name)
        btn.setProperty("class", "tb-btn")
        color = "#ff5470" if name == "TbClose" else "#9a9aa6"
        btn.setIcon(icons.icon(glyph, color))
        btn.setFixedSize(40, 46)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(signal.emit)
        return btn

    def set_settings_open(self, is_open: bool) -> None:
        self.gear_btn.setProperty("settingsOpen", "true" if is_open else "false")
        color = "#b974ff" if is_open else "#9a9aa6"
        self.gear_btn.setIcon(icons.icon("gear", color))
        style = self.gear_btn.style()
        style.unpolish(self.gear_btn)
        style.polish(self.gear_btn)

    # -- window drag ----------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window()
            self._drag_offset = event.globalPosition().toPoint() - window.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(event)
