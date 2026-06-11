"""Configuration persistence for ytdlpgui (Stream A).

Loads/saves a JSON file from:
  - $YTDLPGUI_CONFIG_DIR/config.json  (if env var is set — used by tests)
  - %LOCALAPPDATA%\\ytdlpgui\\config.json  (production default)

Seeded from contracts.CONFIG_DEFAULTS; missing or unknown keys fall back to
defaults, making forward/backward migration safe.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.core.contracts import (
    CONFIG_DEFAULTS,
    PRESET_BEST,
    CookieSource,
    DownloadMode,
    DownloadOptions,
)


class Config:
    """Persistent key-value store backed by a JSON file.

    Implements contracts.IConfig (structurally — no explicit inheritance needed).
    Instantiate normally; no singleton enforced so tests can create isolated
    instances via the YTDLPGUI_CONFIG_DIR env var.
    """

    def __init__(self) -> None:
        self._path: Path = self._resolve_path()
        self._data: dict[str, Any] = dict(CONFIG_DEFAULTS)  # start with defaults
        self._load()

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_path() -> Path:
        env_dir = os.environ.get("YTDLPGUI_CONFIG_DIR")
        if env_dir:
            config_dir = Path(env_dir)
        else:
            local_app_data = os.environ.get("LOCALAPPDATA", "")
            if local_app_data:
                config_dir = Path(local_app_data) / "ytdlpgui"
            else:
                # Fallback for non-Windows environments (e.g. CI)
                config_dir = Path.home() / ".ytdlpgui"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.json"

    # ------------------------------------------------------------------
    # IConfig protocol
    # ------------------------------------------------------------------

    def get(self, key: str) -> object:
        """Return the value for *key*, falling back to CONFIG_DEFAULTS."""
        return self._data.get(key, CONFIG_DEFAULTS.get(key))

    def set(self, key: str, value: object) -> None:
        """Set *key* to *value* in memory (call save() to persist)."""
        self._data[key] = value

    def save(self) -> None:
        """Write current settings to disk as JSON."""
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Internal load / migration
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load from disk; unknown keys are discarded, missing keys get defaults."""
        if not self._path.exists():
            return  # keep defaults as-is
        try:
            raw: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return  # corrupt file — keep defaults

        # Migration: only accept keys that exist in CONFIG_DEFAULTS.
        # Unknown keys (from a newer version) are silently dropped.
        for key, default in CONFIG_DEFAULTS.items():
            if key in raw:
                self._data[key] = raw[key]
            else:
                self._data[key] = default

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def video_dir(self) -> Path:
        """Resolved absolute path for video downloads."""
        base = Path(str(self._data.get("base_dir", CONFIG_DEFAULTS["base_dir"])))
        sub = str(self._data.get("video_subfolder", CONFIG_DEFAULTS["video_subfolder"]))
        return base / sub

    def audio_dir(self) -> Path:
        """Resolved absolute path for audio downloads."""
        base = Path(str(self._data.get("base_dir", CONFIG_DEFAULTS["base_dir"])))
        sub = str(self._data.get("audio_subfolder", CONFIG_DEFAULTS["audio_subfolder"]))
        return base / sub

    def as_download_options(
        self,
        url: str,
        mode: DownloadMode = DownloadMode.VIDEO,
        format_id: str | None = None,
        preset: str | None = None,
    ) -> DownloadOptions:
        """Build a DownloadOptions from current config + caller-supplied overrides."""
        cookie_source_raw = str(self._data.get("cookies_source", CookieSource.NONE.value))
        try:
            cookie_source = CookieSource(cookie_source_raw)
        except ValueError:
            cookie_source = CookieSource.NONE

        cookies_file_raw = str(self._data.get("cookies_file_path", ""))
        cookies_file: Path | None = Path(cookies_file_raw) if cookies_file_raw else None

        browser_raw = self._data.get("browser_choice", None)
        browser: str | None = str(browser_raw) if browser_raw else None

        subtitle_langs_raw = self._data.get("subtitle_langs", CONFIG_DEFAULTS["subtitle_langs"])
        if isinstance(subtitle_langs_raw, list):
            subtitle_langs: list[str] = [str(x) for x in subtitle_langs_raw]
        else:
            subtitle_langs = ["en", "tr"]

        effective_preset = (
            preset if preset is not None else str(self._data.get("default_preset", PRESET_BEST))
        )
        return DownloadOptions(
            url=url,
            mode=mode,
            format_id=format_id,
            preset=effective_preset,
            video_dir=self.video_dir(),
            audio_dir=self.audio_dir(),
            audio_format=str(self._data.get("audio_format", CONFIG_DEFAULTS["audio_format"])),
            cookie_source=cookie_source,
            browser=browser,
            cookies_file=cookies_file,
            subtitle_langs=subtitle_langs,
            write_auto_subs=bool(self._data.get("write_auto_subs", False)),
            embed_subs=bool(self._data.get("embed_subs", False)),
            embed_thumbnail=bool(self._data.get("embed_thumbnail", False)),
            embed_metadata=bool(self._data.get("embed_metadata", False)),
            concurrent_fragments=int(
                self._data.get(
                    "concurrent_fragments",
                    CONFIG_DEFAULTS["concurrent_fragments"],
                )
            ),
        )
