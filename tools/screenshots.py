"""Render app screenshots to docs/assets/screenshots/ without a real download.

Builds the real MainWindow with a mock fetcher (sample metadata) and grabs the
window to PNG in a few states. Run from the repo root:

    python tools/screenshots.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

# Clean, isolated config so fields show their defaults/placeholders.
os.environ.setdefault("YTDLPGUI_CONFIG_DIR", tempfile.mkdtemp(prefix="ytg-shots-"))

# Allow running as `python tools/screenshots.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import contracts as c  # noqa: E402
from app.core.config import Config  # noqa: E402
from app.main import _apply_static_dark_theme  # noqa: E402
from app.main_window import MainWindow, load_qss  # noqa: E402

OUT = Path("docs/assets/screenshots")


class _MockRunner:
    def set_callbacks(self, on_progress: object, on_log: object, on_finished: object) -> None:
        self._on_progress = on_progress

    def start(self, options: c.DownloadOptions) -> None:
        pass

    def cancel(self) -> None:
        pass


def _runner_factory() -> _MockRunner:
    return _MockRunner()


class _MockFetcher:
    """Returns sample metadata + formats synchronously."""

    def fetch_formats(
        self,
        url: str,
        on_done: Callable[[c.MediaInfo, list[c.FormatInfo]], None],
        on_error: Callable[[c.AppError], None],
    ) -> None:
        media = c.MediaInfo(
            title="Rick Astley - Never Gonna Give You Up (Official Video)",
            channel="Rick Astley",
            duration=213,
            subtitle_langs=["en", "tr", "de", "es", "fr"],
        )
        formats = [
            c.FormatInfo(format_id="313", ext="webm", resolution="3840x2160", fps=30, vcodec="vp9"),
            c.FormatInfo(format_id="137", ext="mp4", resolution="1920x1080", fps=30, vcodec="h264"),
            c.FormatInfo(format_id="136", ext="mp4", resolution="1280x720", fps=30, vcodec="h264"),
            c.FormatInfo(format_id="135", ext="mp4", resolution="854x480", fps=30, vcodec="h264"),
            c.FormatInfo(format_id="140", ext="m4a", resolution="audio only", acodec="aac"),
        ]
        on_done(media, formats)

    def expand_playlist(self, url: str, on_done: object, on_error: object) -> None:
        pass


def _settle(app: QApplication, ms: int = 450) -> None:
    """Spin the event loop so any (reduced) animation/layout finishes before grab."""
    import time

    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def _save(window: MainWindow, app: QApplication, name: str) -> None:
    _settle(app)
    path = OUT / name
    window.grab().save(str(path))
    print(f"saved {path}")


def main() -> int:
    app = QApplication(sys.argv)
    _apply_static_dark_theme(app)
    app.setStyleSheet(load_qss("purple"))
    OUT.mkdir(parents=True, exist_ok=True)

    window = MainWindow(_MockFetcher(), _runner_factory, Config(), reduced_motion=True)
    window.resize(1100, 780)
    window.show()

    # 1) First-launch / empty state (before any fetch).
    _save(window, app, "empty.png")

    # 2) After a fetch — sample meme video (rickroll).
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    window.omni.input.setText(url)
    window._on_fetch(url)  # noqa: SLF001 — mock returns synchronously
    _save(window, app, "app.png")

    # 3) Settings panel.
    window.toggle_settings(True)
    _save(window, app, "settings.png")

    return 0


if __name__ == "__main__":
    sys.exit(main())
