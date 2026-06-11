"""Omni-bar: hero heading + URL input + Fetch button (hero → docked).

URL regex validation enables Fetch; Enter triggers Fetch when valid. The hero
heading hides and the top margin animates 56→28 after the first fetch/error.
"""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import icons
from app.ui_state import URL_RE

_URL_RE = re.compile(URL_RE, re.IGNORECASE)


class OmniBar(QWidget):
    """Hero omni-bar with manual Fetch button and URL validation."""

    fetch_requested = Signal(str)

    def __init__(self, reduced_motion: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reduced_motion = reduced_motion
        self._fetching = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._hero = QWidget()
        hero_layout = QVBoxLayout(self._hero)
        hero_layout.setContentsMargins(0, 0, 0, 24)
        hero_layout.setSpacing(6)
        title = QLabel("Paste a link, get the media.")
        title.setObjectName("HeroTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("Video, audio or subtitles — fetched with yt-dlp, queued below.")
        sub.setObjectName("HeroSub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(title)
        hero_layout.addWidget(sub)
        outer.addWidget(self._hero)

        bar = QWidget()
        bar.setObjectName("OmniBar")
        self._bar = bar
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(8, 8, 8, 8)
        bar_layout.setSpacing(10)

        link = QLabel()
        link.setPixmap(icons.pixmap("link", "#6b6b78", 16))
        bar_layout.addWidget(link)

        self.input = QLineEdit()
        self.input.setObjectName("OmniInput")
        self.input.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self.input.textChanged.connect(self._on_text_changed)
        self.input.returnPressed.connect(self._on_return)
        bar_layout.addWidget(self.input, 1)

        self.fetch_btn = QPushButton("Fetch")
        self.fetch_btn.setObjectName("FetchBtn")
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fetch_btn.clicked.connect(self._on_return)
        bar_layout.addWidget(self.fetch_btn)
        outer.addWidget(bar)

    # -- validation -----------------------------------------------------------
    @staticmethod
    def is_valid_url(url: str) -> bool:
        return bool(_URL_RE.match(url.strip()))

    def _on_text_changed(self, text: str) -> None:
        valid = self.is_valid_url(text)
        self.fetch_btn.setEnabled(valid and not self._fetching)

    def _on_return(self) -> None:
        if self._fetching:
            return
        text = self.input.text().strip()
        if self.is_valid_url(text):
            self.fetch_requested.emit(text)

    # -- states ---------------------------------------------------------------
    def set_fetching(self, fetching: bool) -> None:
        self._fetching = fetching
        if fetching:
            self.fetch_btn.setText("Fetching")
            self.fetch_btn.setEnabled(False)
        else:
            self.fetch_btn.setText("Fetch")
            self.fetch_btn.setEnabled(self.is_valid_url(self.input.text()))

    def set_docked(self, docked: bool) -> None:
        """Hide the hero heading once docked (margin handled by the layout)."""
        self._hero.setVisible(not docked)

    def set_focused_style(self, focused: bool) -> None:
        self._bar.setProperty("focused", "true" if focused else "false")
        style = self._bar.style()
        style.unpolish(self._bar)
        style.polish(self._bar)
