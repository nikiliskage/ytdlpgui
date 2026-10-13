"""Playlist Card: the playlist's videos as a checklist + one mode/quality for all.

Shown instead of the Media Card when a link resolves to a playlist. Each checked
video becomes its own queue job (so it can be canceled/retried on its own),
saved as ``<video|audio dir>\\<playlist title>\\NN - <title>.<ext>``.

Keeps its own mode/quality/subtitle selection (it never touches the Media
Card's UiState), and the main window reads it via ``mode()``/``quality()``/
``subs()`` when queueing.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import icons
from app.core import contracts as c
from app.core.filenames import sanitize_filename
from app.ui_state import format_duration
from app.widgets.quality_chips import QualityChips
from app.widgets.segmented_switch import SegmentedSwitch
from app.widgets.subtitle_chips import SubtitleChips

_LIST_MAX_HEIGHT = 300


class PlaylistCard(QWidget):
    """Checklist of a playlist's videos with a shared mode/quality picker."""

    add_selected = Signal()

    def __init__(
        self,
        reduced_motion: bool = False,
        parent: QWidget | None = None,
        config: c.IConfig | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PlaylistCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._config = config
        self._playlist: c.PlaylistInfo | None = None
        self._syncing = False  # suppress per-item signals while (un)checking all

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(0)

        # head -----------------------------------------------------------------
        self._title = QLabel("—")
        self._title.setObjectName("McTitle")
        self._title.setWordWrap(True)
        self._count = QLabel("")
        self._count.setObjectName("PlCount")
        self._count.setContentsMargins(0, 6, 0, 0)
        layout.addWidget(self._title)
        layout.addWidget(self._count)

        # mode + quality (same widgets as the media card; no format table, since
        # formats differ per video) ---------------------------------------------
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 18, 0, 0)
        controls.setSpacing(14)
        self.segmented = SegmentedSwitch(reduced_motion)
        self.segmented.mode_changed.connect(self._on_mode_changed)
        controls.addWidget(self.segmented)
        self.chips = QualityChips()
        controls.addWidget(self.chips, 1)
        self.sub_chips = SubtitleChips()
        self.sub_chips.setVisible(False)
        controls.addWidget(self.sub_chips, 1)
        layout.addLayout(controls)

        # checklist ------------------------------------------------------------
        self.select_all = QCheckBox("Select all")
        self.select_all.setTristate(False)
        self.select_all.clicked.connect(self._on_select_all)
        sel_row = QHBoxLayout()
        sel_row.setContentsMargins(0, 18, 0, 8)
        sel_row.addWidget(self.select_all)
        sel_row.addStretch(1)
        layout.addLayout(sel_row)

        self.list = QListWidget()
        self.list.setObjectName("PlList")
        self.list.setMaximumHeight(_LIST_MAX_HEIGHT)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.itemChanged.connect(self._on_item_changed)
        # Enter / double-click toggles a row (a plain click on the checkbox
        # already does; hooking itemClicked would toggle it twice).
        self.list.itemActivated.connect(self._toggle_item)
        layout.addWidget(self.list)

        # footer ---------------------------------------------------------------
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 18, 0, 0)
        footer.setSpacing(12)
        folder = QLabel()
        folder.setObjectName("McDest")
        folder.setPixmap(icons.pixmap("folder", "#6b6b78", 14))
        self._dest_label = QLabel()
        self._dest_label.setObjectName("McDest")
        footer.addWidget(folder)
        footer.addWidget(self._dest_label, 1)
        self.queue_btn = QPushButton("Add to queue")
        self.queue_btn.setObjectName("QueueBtn")
        self.queue_btn.setIcon(icons.icon("download", "#ffffff"))
        self.queue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.queue_btn.clicked.connect(self.add_selected.emit)
        footer.addWidget(self.queue_btn)
        layout.addLayout(footer)

        self.chips.set_mode(c.DownloadMode.VIDEO)

    # -- populate -------------------------------------------------------------
    def set_playlist(self, playlist: c.PlaylistInfo) -> None:
        """Show *playlist*; every video starts checked."""
        self._playlist = playlist
        self._title.setText(playlist.title)
        self._syncing = True
        self.list.clear()
        for item in playlist.items:
            dur = f"   ·  {format_duration(item.duration)}" if item.duration else ""
            row = QListWidgetItem(f"{item.index:02d}   {item.title}{dur}")
            row.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            row.setCheckState(Qt.CheckState.Checked)
            row.setToolTip(item.title)
            row.setData(Qt.ItemDataRole.UserRole, item)
            self.list.addItem(row)
        self._syncing = False
        self.refresh_dest()
        self.refresh_subtitles()
        self._update_selection_ui()

    # -- selection ------------------------------------------------------------
    def selected_items(self) -> list[c.PlaylistItem]:
        """Checked videos, in playlist order."""
        result: list[c.PlaylistItem] = []
        for i in range(self.list.count()):
            row = self.list.item(i)
            if row.checkState() == Qt.CheckState.Checked:
                item = row.data(Qt.ItemDataRole.UserRole)
                if isinstance(item, c.PlaylistItem):
                    result.append(item)
        return result

    def set_checked(self, index: int, checked: bool) -> None:
        """Check/uncheck the row at list position *index* (also used by tests)."""
        row = self.list.item(index)
        if row is not None:
            row.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _toggle_item(self, row: QListWidgetItem) -> None:
        """Toggle a row's checkbox from the keyboard / a double-click."""
        new = (
            Qt.CheckState.Unchecked
            if row.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        row.setCheckState(new)

    def _on_select_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._syncing = True
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)
        self._syncing = False
        self._update_selection_ui()

    def _on_item_changed(self, _row: QListWidgetItem) -> None:
        if not self._syncing:
            self._update_selection_ui()

    def _update_selection_ui(self) -> None:
        total = self.list.count()
        n = len(self.selected_items())
        self._count.setText(f"{total} videos  ·  {n} selected")
        self.select_all.setChecked(total > 0 and n == total)
        self.queue_btn.setEnabled(n > 0)
        self.queue_btn.setText(f"Add {n} to queue")

    # -- mode / quality -------------------------------------------------------
    def mode(self) -> c.DownloadMode:
        return self.segmented.mode()

    def quality(self) -> str | None:
        return self.chips.selected()

    def subs(self) -> list[str]:
        return self.sub_chips.selected()

    def _on_mode_changed(self, mode: object) -> None:
        dl_mode = c.DownloadMode(str(mode))
        is_sub = dl_mode == c.DownloadMode.SUBTITLE
        if not is_sub:
            self.chips.set_mode(dl_mode)
        self.chips.setVisible(not is_sub)
        self.sub_chips.setVisible(is_sub)
        self.refresh_dest()

    def refresh_subtitles(self) -> None:
        """Offer the configured languages; availability per video is unknown."""
        langs = self._configured_subs()
        self.sub_chips.set_langs(langs, set(langs))

    def _configured_subs(self) -> list[str]:
        if self._config is not None:
            try:
                value = self._config.get("subtitle_langs")
            except Exception:
                value = None
            if isinstance(value, list) and value:
                return [str(x) for x in value]
        return ["en", "tr"]

    # -- destination ----------------------------------------------------------
    def subfolder(self) -> str:
        """Folder name the playlist is saved under (sanitized title)."""
        title = self._playlist.title if self._playlist is not None else ""
        return sanitize_filename(title, fallback="Playlist")

    def refresh_dest(self) -> None:
        is_audio = self.mode() == c.DownloadMode.AUDIO
        key = "audio_dir" if is_audio else "video_dir"
        base = "audio" if is_audio else "video"
        if self._config is not None:
            try:
                value = self._config.get(key)
            except Exception:
                value = None
            if value:
                base = Path(str(value)).name or base
        self._dest_label.setText(f"{base}\\{self.subfolder()}\\")
