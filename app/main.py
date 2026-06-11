"""Application entry point: wires the real cores into the UI (Faz 2 integration).

Creates the QApplication, loads the real :class:`Config`, shows the splash while
the real binary/version checks run, then constructs :class:`MainWindow` with the
real :class:`FormatFetcher` and :class:`YtDlpRunner` factory injected.
"""

from __future__ import annotations

import sys

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from app.core import paths
from app.core.config import Config
from app.core.format_fetcher import FormatFetcher
from app.core.ytdlp_runner import YtDlpRunner
from app.main_window import MainWindow
from app.splash import Splash, Step


def _build_steps(config: Config) -> list[Step]:
    """Real startup checklist for the splash (raises on a missing binary)."""

    def load_settings() -> str | None:
        # Config is already loaded by the time we get here.
        return None

    def check_ytdlp() -> str | None:
        status = paths.resolve_ytdlp(str(config.get("ytdlp_path") or ""))
        if not status.found or status.path is None:
            raise RuntimeError("yt-dlp not found")
        return paths.ytdlp_version(status.path)

    def check_ffmpeg() -> str | None:
        status = paths.resolve_ffmpeg(str(config.get("ffmpeg_path") or ""))
        if not status.found or status.path is None:
            raise RuntimeError("ffmpeg not found")
        return paths.ffmpeg_version(status.path)

    return [
        ("Loading settings…", load_settings),
        ("Checking yt-dlp…", check_ytdlp),
        ("Checking ffmpeg…", check_ffmpeg),
    ]


def _center(widget: MainWindow | Splash) -> None:
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return
    geo = screen.availableGeometry()
    frame = widget.frameGeometry()
    frame.moveCenter(geo.center())
    widget.move(frame.topLeft())


def main() -> int:
    app = QApplication(sys.argv)
    config = Config()
    reduced_motion = bool(config.get("reduced_motion"))

    window = MainWindow(FormatFetcher(), YtDlpRunner, config)

    splash = Splash(_build_steps(config), reduced_motion)

    def _show_main() -> None:
        _center(window)
        window.show()

    splash.finished.connect(_show_main)
    splash.show()
    _center(splash)
    splash.run()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
