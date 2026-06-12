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
        ("1080p", "1080p", "mp4"),
        ("720p", "720p", "mp4"),
        ("480p", "480p", "mp4"),
    ],
    c.DownloadMode.AUDIO: [
        ("bestaudio", "Best", "auto"),
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


# Subtitle languages offered as selectable chips (code, display label). Shared by
# the settings panel (which languages to offer) and the media-card subtitle chips.
SUBTITLE_LANGS: list[tuple[str, str]] = [
    ("en", "English"),
    ("tr", "Türkçe"),
    ("de", "Deutsch"),
    ("es", "Español"),
    ("fr", "Français"),
    ("it", "Italiano"),
    ("ru", "Русский"),
    ("ar", "العربية"),
    ("ja", "日本語"),
]

_LANG_LABELS: dict[str, str] = dict(SUBTITLE_LANGS)


def lang_label(code: str) -> str:
    """Human label for a language code (falls back to the code itself)."""
    return _LANG_LABELS.get(code, code)


def _base_lang(code: str) -> str:
    """Primary subtag of a BCP-47-ish code: 'de-DE' / 'de-orig' → 'de'."""
    return code.split("-")[0].lower()


def match_subtitle_code(lang: str, available: list[str]) -> str | None:
    """Find the video's subtitle code for a configured *lang*, region-insensitive.

    Prefers an exact match, then any code sharing the primary subtag (so a
    configured ``de`` matches a video's ``de-DE``). Returns the actual video
    code to request from yt-dlp, or ``None`` if the video has no such subtitle.
    """
    if lang in available:
        return lang
    base = _base_lang(lang)
    return next((code for code in available if _base_lang(code) == base), None)


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
    selected_subs: list[str] = field(default_factory=list)  # subtitle mode (max 2)
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
