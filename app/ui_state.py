"""UI state model for the main window (handoff state machine).

Mirrors the prototype's single store: phase / mode / quality / selected format /
queue / panel open flags. Pure-Python (no Qt), so it can be unit-tested and the
widgets bind to it through the main window.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core import contracts as c

# URL validation regex — matches the handoff `URL_RE`
# (`^https?://<host>.<tld>` with a 2+ char tld).
URL_RE = r"^https?://[^\s.]+\.[^\s]{2,}"


# Quality chip sets per mode — (chip_id, label, suffix). Matches handoff
# `CHIPS_BY_MODE`.
CHIPS_BY_MODE: dict[c.DownloadMode, list[tuple[str, str, str]]] = {
    c.DownloadMode.VIDEO: [
        ("best", "Best", "auto"),
        ("1080", "1080p", "mp4"),
        ("720", "720p", "mp4"),
        ("480", "480p", "mp4"),
    ],
    c.DownloadMode.AUDIO: [
        ("bestaudio", "Best audio", "auto"),
        ("opus", "opus", "160k"),
        ("mp3", "mp3", "320k"),
        ("m4a", "m4a", "128k"),
    ],
    c.DownloadMode.SUBTITLE: [
        ("en", "English", "en"),
        ("tr", "Türkçe", "tr"),
        ("auto", "Auto-generated", "asr"),
    ],
}


def first_chip_id(mode: c.DownloadMode) -> str:
    """First chip id for a mode (used to reset quality on mode switch)."""
    return CHIPS_BY_MODE[mode][0][0]


@dataclass
class UiState:
    """Single source of truth for the main window's interactive state."""

    url: str = ""
    url_valid: bool = False
    phase: c.AppPhase = c.AppPhase.EMPTY
    error: str | None = None

    media: c.MediaInfo | None = None
    formats: list[c.FormatInfo] = field(default_factory=list)

    mode: c.DownloadMode = c.DownloadMode.VIDEO
    quality: str | None = "best"
    selected_format: str | None = None  # mutually exclusive with quality
    advanced_open: bool = False

    queue_open: bool = False
    settings_open: bool = False
    binary_banner: bool = False

    def select_quality(self, chip_id: str) -> None:
        """Pick a quality chip; clears any manual format selection."""
        self.quality = chip_id
        self.selected_format = None

    def select_format(self, format_id: str) -> None:
        """Pick a manual format row; clears the quality chip."""
        self.selected_format = format_id
        self.quality = None

    def set_mode(self, mode: c.DownloadMode) -> None:
        """Switch mode → reset quality to the first chip, clear format."""
        self.mode = mode
        self.quality = first_chip_id(mode)
        self.selected_format = None
