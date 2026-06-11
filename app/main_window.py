"""Frameless main window composing the omni-bar · media card · dock layout.

Dependency-injected: takes a ``fetcher`` (IFormatFetcher), a ``runner_factory``
(RunnerFactory) and a ``config`` (IConfig-like). No Stream A/B/C modules are
imported — only contracts + injected objects — so the UI runs standalone against
the conftest mocks.
"""

from __future__ import annotations

import itertools
from functools import partial
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeyEvent, QResizeEvent
from PySide6.QtWidgets import (
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core import contracts as c
from app.ui_state import UiState
from app.widgets.dock import Dock
from app.widgets.error_band import ErrorBand
from app.widgets.fly_to_dock import fly_to_dock
from app.widgets.media_card import MediaCard
from app.widgets.omni_bar import OmniBar
from app.widgets.queue_panel import QueuePanel
from app.widgets.settings_panel import SettingsPanel
from app.widgets.skeleton import Skeleton
from app.widgets.title_bar import TitleBar

_QSS_PATH = Path(__file__).parent / "resources" / "theme.qss"


def _as_int(value: object, default: int) -> int:
    """Coerce a config value (object) to int, falling back to default."""
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def load_qss(accent: str = "purple") -> str:
    """Read theme.qss, optionally swapping the accent recipe."""
    text = _QSS_PATH.read_text(encoding="utf-8")
    swaps = {
        "indigo": ("#7c6cf7", "#988bff"),
        "pink": ("#f25f9e", "#ff82b6"),
    }
    if accent in swaps:
        accent_hex, hover_hex = swaps[accent]
        text = text.replace("#a855f7", accent_hex).replace("#b974ff", hover_hex)
    return text


class MainWindow(QWidget):
    """The application's main window (frameless, custom chrome)."""

    def __init__(
        self,
        fetcher: c.IFormatFetcher,
        runner_factory: c.RunnerFactory,
        config: c.IConfig,
        reduced_motion: bool | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fetcher = fetcher
        self._runner_factory = runner_factory
        self._config = config
        if reduced_motion is None:
            reduced_motion = bool(self._cfg("reduced_motion", False))
        self._reduced_motion = reduced_motion
        self.state = UiState()
        self._ids = itertools.count(1)
        self._runners: dict[str, c.IYtDlpRunner] = {}
        self._max_concurrent = _as_int(self._cfg("max_concurrent_downloads", 2), 2)

        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(1100, 720)
        self.setObjectName("AppWindow")

        self._build()
        accent = str(self._cfg("accent_theme", "purple"))
        self.setStyleSheet(load_qss(accent))

    def _cfg(self, key: str, default: object) -> object:
        try:
            value = self._config.get(key)
        except Exception:
            return default
        return value if value is not None else default

    # -- layout ---------------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        root = QWidget()
        root.setObjectName("AppRoot")
        outer.addWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = TitleBar()
        self.title_bar.gear_clicked.connect(self.toggle_settings)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self._toggle_max)
        self.title_bar.close_clicked.connect(self.close)
        root_layout.addWidget(self.title_bar)

        # scrollable content
        self._scroll = QScrollArea()
        self._scroll.setObjectName("MainArea")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(48, 56, 48, 24)
        self._content_layout.setSpacing(0)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        self.omni = OmniBar(self._reduced_motion)
        self.omni.setMaximumWidth(760)
        self.omni.fetch_requested.connect(self._on_fetch)
        self._content_layout.addWidget(self.omni, 0, Qt.AlignmentFlag.AlignHCenter)

        self.error_band = ErrorBand()
        self.error_band.setMaximumWidth(760)
        self.error_band.retry.connect(self._retry)
        self.error_band.setVisible(False)
        self._content_layout.addWidget(self.error_band, 0, Qt.AlignmentFlag.AlignHCenter)

        self.skeleton = Skeleton(self._reduced_motion)
        self.skeleton.setMaximumWidth(760)
        self.skeleton.setVisible(False)
        self._content_layout.addSpacing(22)
        self._content_layout.addWidget(self.skeleton, 0, Qt.AlignmentFlag.AlignHCenter)

        self.media_card = MediaCard(self.state, self._reduced_motion)
        self.media_card.setMaximumWidth(760)
        self.media_card.setVisible(False)
        self.media_card.add_to_queue.connect(self._on_add_to_queue)
        self.media_card.enable_cookies.connect(self._on_enable_cookies)
        self._content_layout.addWidget(self.media_card, 0, Qt.AlignmentFlag.AlignHCenter)
        self._content_layout.addStretch(1)

        self._scroll.setWidget(content)
        root_layout.addWidget(self._scroll, 1)

        # dock
        self.dock = Dock(self._reduced_motion)
        self.dock.item_clicked.connect(lambda _id: self._open_queue(True))
        self.dock.expand_clicked.connect(self._toggle_queue)
        root_layout.addWidget(self.dock)

        # overlays (children of root, manually positioned)
        self.scrim = QWidget(root)
        self.scrim.setObjectName("Scrim")
        self.scrim.setVisible(False)
        self.scrim.mousePressEvent = lambda _e: self._close_overlays()  # type: ignore[method-assign]

        self.queue_panel = QueuePanel(self._reduced_motion, root)
        self.queue_panel.clear_completed.connect(self._clear_completed)
        self.queue_panel.setVisible(False)

        self.settings_panel = SettingsPanel(self._config, self._reduced_motion, root)
        self.settings_panel.close_requested.connect(lambda: self.toggle_settings(False))
        self.settings_panel.setVisible(False)

        self._root = root

    def _toggle_max(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # -- fetch flow -----------------------------------------------------------
    def _on_fetch(self, url: str) -> None:
        self.state.url = url
        self.state.phase = c.AppPhase.FETCHING
        self.omni.set_fetching(True)
        self.omni.set_docked(True)
        self.error_band.setVisible(False)
        self.media_card.setVisible(False)
        self.skeleton.setVisible(True)
        self._fetcher.fetch_formats(url, self._on_fetch_done, self._on_fetch_error)

    def _on_fetch_done(self, media: c.MediaInfo, formats: list[c.FormatInfo]) -> None:
        self.state.phase = c.AppPhase.LOADED
        self.state.media = media
        self.state.formats = formats
        self.omni.set_fetching(False)
        self.skeleton.setVisible(False)
        self.error_band.setVisible(False)
        self.media_card.set_media(media, formats)
        self.media_card.setVisible(True)

    def _on_fetch_error(self, error: c.AppError) -> None:
        self.state.phase = c.AppPhase.EMPTY
        self.state.error = error.user_message
        self.omni.set_fetching(False)
        self.skeleton.setVisible(False)
        self.media_card.setVisible(False)
        self.error_band.set_message(error.user_message or error.raw or "Unknown error.")
        self.error_band.setVisible(True)

    def _retry(self) -> None:
        if self.state.url:
            self._on_fetch(self.state.url)

    # -- queue ----------------------------------------------------------------
    def _on_add_to_queue(self) -> None:
        media = self.state.media
        title = media.title if media else "Download"
        job_id = f"job-{next(self._ids)}"
        self.dock.add_item(job_id, title)
        self.queue_panel.add_row(job_id, title)

        # fly-to-dock from the Add-to-queue button to the dock chevron
        host = self._root
        btn = self.media_card.queue_btn
        start_global = btn.mapToGlobal(btn.rect().center())
        start = host.mapFromGlobal(start_global)
        end_x, end_y = self.dock.queue_btn_geometry_center()
        end_global = self.dock.mapToGlobal(QPoint(0, 0))
        end = host.mapFromGlobal(end_global) + QPoint(end_x, end_y - 86)
        if not self._reduced_motion:
            fly_to_dock(host, start, QPoint(end.x(), end.y()), self._reduced_motion)

        # build options + runner
        options = self._build_options()
        runner = self._runner_factory()
        self._runners[job_id] = runner
        runner.set_callbacks(
            partial(self._on_progress, job_id),
            lambda line: None,
            partial(self._on_finished, job_id),
        )
        self.dock.set_state(job_id, c.JobState.RUNNING)
        row = self.queue_panel.row(job_id)
        if row is not None:
            row.set_state(c.JobState.RUNNING)
        runner.start(options)

    def _build_options(self) -> c.DownloadOptions:
        opts = c.DownloadOptions(url=self.state.url, mode=self.state.mode)
        if self.state.selected_format:
            opts.format_id = self.state.selected_format
            opts.preset = None
        else:
            opts.preset = self.state.quality
        return opts

    def _on_progress(self, job_id: str, progress: c.Progress) -> None:
        self.dock.update_progress(job_id, progress)
        row = self.queue_panel.row(job_id)
        if row is not None:
            row.update_progress(progress)

    def _on_finished(self, job_id: str, state: c.JobState, error: c.AppError | None) -> None:
        self.dock.set_state(job_id, state)
        row = self.queue_panel.row(job_id)
        if row is not None:
            msg = error.user_message if error else ""
            row.set_state(state, msg)

    def _clear_completed(self) -> None:
        for job_id, item in list(self.dock._items.items()):  # noqa: SLF001
            if item.ring.state() == c.JobState.COMPLETED:
                self.dock.remove_item(job_id)
                self.queue_panel.remove_row(job_id)
        if not self.queue_panel.rows():
            self._open_queue(False)

    # -- overlays -------------------------------------------------------------
    def toggle_settings(self, force: bool | None = None) -> None:
        is_open = not self.settings_panel.is_open() if force is None else force
        self._open_queue(False)
        self.settings_panel.set_open(is_open)
        self.title_bar.set_settings_open(is_open)
        self.scrim.setVisible(is_open)
        if is_open:
            self.scrim.raise_()
            self.settings_panel.raise_()
        self._layout_overlays()

    def _toggle_queue(self) -> None:
        self._open_queue(not self.queue_panel.is_open())

    def _open_queue(self, is_open: bool) -> None:
        self.queue_panel.set_open(is_open)
        if is_open:
            self.queue_panel.raise_()
        self._layout_overlays()

    def _on_enable_cookies(self) -> None:
        self.toggle_settings(True)
        self.settings_panel.enable_cookies_module()

    def _close_overlays(self) -> None:
        self.toggle_settings(False)
        self._open_queue(False)
        self.scrim.setVisible(False)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._close_overlays()
        super().keyPressEvent(event)

    # -- overlay geometry -----------------------------------------------------
    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._layout_overlays()

    def _layout_overlays(self) -> None:
        if not hasattr(self, "_root"):
            return
        w, h = self._root.width(), self._root.height()
        self.scrim.setGeometry(0, 0, w, h)
        self.settings_panel.setGeometry(w - 380, 0, 380, h)
        dock_top = h - 86
        self.queue_panel.setGeometry(0, max(0, dock_top - 380), w, 380)
