"""Media Card: thumbnail + meta, mode switch, quality chips, advanced table,
optional cookie band, and an Add-to-queue footer.

Coordinates the mutual exclusion between quality chips and a manual format row,
and resets quality / clears the table / hides Advanced when the mode switches.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import icons
from app.core import contracts as c
from app.ui_state import UiState, first_chip_id, match_subtitle_code
from app.widgets.format_table import FormatTable
from app.widgets.quality_chips import QualityChips
from app.widgets.segmented_switch import SegmentedSwitch
from app.widgets.subtitle_chips import SubtitleChips


def _fmt_duration(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class _Thumb(QWidget):
    """Placeholder thumbnail with a duration badge (real thumb at runtime)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(200, 112)
        self._duration = ""

    def set_duration(self, text: str) -> None:
        self._duration = text
        self.update()

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#34343e"))
        painter.setBrush(QColor("#26233a"))
        painter.drawRoundedRect(0, 0, 199, 111, 10, 10)
        if self._duration:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 190))
            badge_w = 7 * len(self._duration) + 14
            painter.drawRoundedRect(200 - badge_w - 6, 112 - 24, badge_w, 18, 5, 5)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                200 - badge_w - 6,
                112 - 24,
                badge_w,
                18,
                Qt.AlignmentFlag.AlignCenter,
                self._duration,
            )
        painter.end()


class MediaCard(QWidget):
    """The central media card; owns mode/quality/format selection widgets."""

    add_to_queue = Signal()
    enable_cookies = Signal()

    def __init__(
        self,
        state: UiState,
        reduced_motion: bool = False,
        parent: QWidget | None = None,
        config: c.IConfig | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MediaCard")
        self._state = state
        self._config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(0)

        # head row (title + channel/duration; thumbnail intentionally omitted) ---
        head = QHBoxLayout()
        head.setSpacing(18)

        meta = QVBoxLayout()
        meta.setSpacing(6)
        self._title = QLabel("—")
        self._title.setObjectName("McTitle")
        self._title.setWordWrap(True)
        self._channel = QLabel("—")
        self._channel.setObjectName("McChannel")
        meta.addWidget(self._title)
        meta.addWidget(self._channel)
        meta.addStretch(1)

        self._cookie_band = self._build_cookie_band()
        self._cookie_band.setVisible(False)
        meta.addWidget(self._cookie_band)
        head.addLayout(meta, 1)
        layout.addLayout(head)

        # controls row ---------------------------------------------------------
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 18, 0, 0)
        controls.setSpacing(14)
        self.segmented = SegmentedSwitch(reduced_motion)
        self.segmented.mode_changed.connect(self._on_mode_changed)
        controls.addWidget(self.segmented)
        self.chips = QualityChips()
        self.chips.chip_selected.connect(self._on_chip_selected)
        controls.addWidget(self.chips, 1)
        self.sub_chips = SubtitleChips()
        self.sub_chips.changed.connect(self._on_subs_changed)
        self.sub_chips.setVisible(False)
        controls.addWidget(self.sub_chips, 1)
        layout.addLayout(controls)

        # note shown in subtitle mode when some configured language is missing
        self._sub_note = QLabel("Greyed-out languages have no subtitle for this video.")
        self._sub_note.setStyleSheet("font-size:11px;color:#6b6b78;")
        self._sub_note.setContentsMargins(0, 8, 0, 0)
        self._sub_note.setVisible(False)
        layout.addWidget(self._sub_note)

        # advanced formats -----------------------------------------------------
        self.formats = FormatTable(reduced_motion)
        self.formats.format_selected.connect(self._on_format_selected)
        adv_wrap = QWidget()
        adv_layout = QVBoxLayout(adv_wrap)
        adv_layout.setContentsMargins(0, 16, 0, 0)
        adv_layout.addWidget(self.formats)
        layout.addWidget(adv_wrap)

        # footer ---------------------------------------------------------------
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 18, 0, 0)
        footer.setSpacing(12)
        self._dest = QLabel()
        self._dest.setObjectName("McDest")
        self._dest.setPixmap(icons.pixmap("folder", "#6b6b78", 14))
        self._dest_label = QLabel(self._dest_name(self._state.mode == c.DownloadMode.AUDIO))
        self._dest_label.setObjectName("McDest")
        footer.addWidget(self._dest)
        footer.addWidget(self._dest_label)
        footer.addStretch(1)
        self.queue_btn = QPushButton("Add to queue")
        self.queue_btn.setObjectName("QueueBtn")
        self.queue_btn.setIcon(icons.icon("download", "#ffffff"))
        self.queue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.queue_btn.clicked.connect(self.add_to_queue.emit)
        footer.addWidget(self.queue_btn)
        layout.addLayout(footer)

        # init mode/chips
        self.chips.set_mode(c.DownloadMode.VIDEO)
        self.formats.set_open(False)

    def _build_cookie_band(self) -> QWidget:
        band = QWidget()
        band.setObjectName("CookieBand")
        row = QHBoxLayout(band)
        row.setContentsMargins(11, 7, 11, 7)
        row.setSpacing(9)
        icon = QLabel()
        icon.setPixmap(icons.pixmap("cookie", "#d9c08a", 14))
        row.addWidget(icon)
        text = QLabel("This video needs sign-in cookies to download.")
        row.addWidget(text, 1)
        link = QPushButton("Enable cookies")
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.clicked.connect(self.enable_cookies.emit)
        row.addWidget(link)
        return band

    # -- destination label ----------------------------------------------------
    def _dest_name(self, is_audio: bool) -> str:
        """Footer label = the configured subfolder name (e.g. 'videosad\\')."""
        key = "audio_subfolder" if is_audio else "video_subfolder"
        name = "musics" if is_audio else "videos"
        if self._config is not None:
            try:
                value = self._config.get(key)
            except Exception:
                value = None
            if value:
                name = str(value)
        return f"{name}\\"

    def refresh_dest(self) -> None:
        """Re-read the configured folder name (call after settings may change)."""
        self._dest_label.setText(self._dest_name(self._state.mode == c.DownloadMode.AUDIO))

    def refresh_subtitles(self) -> None:
        """Re-read configured subtitle languages (call after settings change)."""
        if self._state.mode == c.DownloadMode.SUBTITLE:
            self._refresh_subs()

    # -- populate -------------------------------------------------------------
    def set_media(self, media: c.MediaInfo, formats: list[c.FormatInfo]) -> None:
        self._state.media = media  # availability source for subtitle chips
        self._title.setText(media.title)
        channel = media.channel or "—"
        dur = _fmt_duration(media.duration)
        self._channel.setText(f"{channel}  ·  {dur}")
        self._cookie_band.setVisible(media.needs_cookies)
        self.formats.set_formats(formats)
        self.refresh_dest()
        if self._state.mode == c.DownloadMode.SUBTITLE:
            self._refresh_subs()  # availability is known now

    # -- selection logic ------------------------------------------------------
    def _on_mode_changed(self, mode: object) -> None:
        dl_mode = c.DownloadMode(str(mode))
        self._state.set_mode(dl_mode)
        is_sub = dl_mode == c.DownloadMode.SUBTITLE
        if not is_sub:
            self.chips.set_mode(dl_mode)
        self.chips.setVisible(not is_sub)
        self.sub_chips.setVisible(is_sub)
        self.formats.clear_selection()
        self.formats.set_visible_section(not is_sub)
        self._dest_label.setText(self._dest_name(dl_mode == c.DownloadMode.AUDIO))
        if is_sub:
            self._refresh_subs()
        else:
            self._sub_note.setVisible(False)

    # -- subtitle languages ---------------------------------------------------
    def _configured_subs(self) -> list[str]:
        """Languages the user picked in Settings (fallback: en, tr)."""
        if self._config is not None:
            try:
                value = self._config.get("subtitle_langs")
            except Exception:
                value = None
            if isinstance(value, list) and value:
                return [str(x) for x in value]
        return ["en", "tr"]

    def _refresh_subs(self) -> None:
        """Rebuild subtitle chips from settings + this video's manual subtitles.

        A configured language counts as available if the video has a manual
        subtitle in it, matching region variants (de ↔ de-DE).
        """
        media = self._state.media
        codes = media.subtitle_langs if media is not None else []
        configured = self._configured_subs()
        available = {c for c in configured if match_subtitle_code(c, codes) is not None}
        self.sub_chips.set_langs(configured, available)
        self._sub_note.setVisible(self.sub_chips.has_unavailable())

    def _on_subs_changed(self, langs: list[str]) -> None:
        self._state.selected_subs = list(langs)

    def _on_chip_selected(self, chip_id: str) -> None:
        self._state.select_quality(chip_id)
        self.formats.clear_selection()

    def _on_format_selected(self, format_id: str) -> None:
        self._state.select_format(format_id)
        self.chips.clear_selection()

    def reset_quality(self) -> None:
        self.chips.select(first_chip_id(self._state.mode))
