"""Application entry point: wires the real cores into the UI (Faz 2 integration).

Creates the QApplication, loads the real :class:`Config`, shows the splash while
the real binary/version checks run, then constructs :class:`MainWindow` with the
real :class:`FormatFetcher` and :class:`YtDlpRunner` factory injected.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from app.core import paths
from app.core.config import Config
from app.core.format_fetcher import FormatFetcher
from app.core.ytdlp_runner import YtDlpRunner
from app.main_window import MainWindow, load_qss
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


def _apply_static_dark_theme(app: QApplication) -> None:
    """Force a fixed Fusion style + dark palette so the UI never follows the OS
    light/dark theme (native widgets like the window/close buttons would
    otherwise turn light on a light Windows theme)."""
    app.setStyle("Fusion")
    pal = QPalette()
    bg, base, surface, text, muted, accent = (
        QColor("#1a1a1f"),
        QColor("#1a1a1f"),
        QColor("#24242c"),
        QColor("#e8e8ee"),
        QColor("#6b6b78"),
        QColor("#a855f7"),
    )
    pal.setColor(QPalette.ColorRole.Window, bg)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, base)
    pal.setColor(QPalette.ColorRole.AlternateBase, surface)
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.Button, surface)
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.ToolTipBase, surface)
    pal.setColor(QPalette.ColorRole.ToolTipText, text)
    pal.setColor(QPalette.ColorRole.PlaceholderText, muted)
    pal.setColor(QPalette.ColorRole.Highlight, accent)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, muted)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, muted)
    app.setPalette(pal)


def _apply_app_icon(app: QApplication) -> None:
    """Set the running app's icon (taskbar + windows).

    The PyInstaller ``icon=`` only sets the .exe file icon; the taskbar entry of
    the *running* process uses the window icon. On Windows we also claim an
    explicit AppUserModelID so the taskbar shows our icon instead of grouping
    under the host (python/pythonw) default.
    """
    icon_path = Path(__file__).parent / "resources" / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    if sys.platform == "win32":
        with contextlib.suppress(Exception):
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ytdlpgui.app")


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
    _apply_static_dark_theme(app)
    _apply_app_icon(app)
    config = Config()
    # Apply the theme app-wide so every top-level widget (splash included) is
    # styled — a stylesheet set only on the main window would not reach the splash.
    app.setStyleSheet(load_qss(str(config.get("accent_theme") or "purple")))
    reduced_motion = bool(config.get("reduced_motion"))

    window = MainWindow(FormatFetcher(config), YtDlpRunner, config)

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
