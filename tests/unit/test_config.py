"""Tests for app.core.config — Config persistence and migration (Stream A)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.core.config import Config
from app.core.contracts import CONFIG_DEFAULTS, CookieSource, DownloadMode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config_file(tmp_path: Path) -> Path:
    return tmp_path / "config.json"


# ---------------------------------------------------------------------------
# Basic construction and defaults
# ---------------------------------------------------------------------------


def test_config_initialises_with_defaults(tmp_config: Config) -> None:
    """Fresh Config contains all keys from CONFIG_DEFAULTS."""
    for key, default_value in CONFIG_DEFAULTS.items():
        assert tmp_config.get(key) == default_value, f"key={key!r} mismatch"


def test_config_get_unknown_key_returns_none(tmp_config: Config) -> None:
    """Requesting a key that has never existed returns None."""
    assert tmp_config.get("this_key_does_not_exist") is None


# ---------------------------------------------------------------------------
# Round-trip: set → save → reload
# ---------------------------------------------------------------------------


def test_config_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Changes persist across Config instances pointing at the same directory."""
    monkeypatch.setenv("YTDLPGUI_CONFIG_DIR", str(tmp_path))

    cfg1 = Config()
    cfg1.set("audio_format", "mp3")
    cfg1.set("max_concurrent_downloads", 4)
    cfg1.save()

    cfg2 = Config()
    assert cfg2.get("audio_format") == "mp3"
    assert cfg2.get("max_concurrent_downloads") == 4


def test_config_save_creates_json_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """save() writes a readable JSON file."""
    monkeypatch.setenv("YTDLPGUI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save()

    config_file = _config_file(tmp_path)
    assert config_file.exists()
    data = json.loads(config_file.read_text(encoding="utf-8"))
    assert "base_dir" in data


# ---------------------------------------------------------------------------
# Migration: missing key falls back to default
# ---------------------------------------------------------------------------


def test_config_missing_key_gets_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A config file that is missing a key uses CONFIG_DEFAULTS for that key."""
    monkeypatch.setenv("YTDLPGUI_CONFIG_DIR", str(tmp_path))

    # Write a partial config that deliberately omits 'embed_thumbnail'.
    partial: dict[str, object] = {k: v for k, v in CONFIG_DEFAULTS.items()}
    del partial["embed_thumbnail"]
    _config_file(tmp_path).write_text(json.dumps(partial), encoding="utf-8")

    cfg = Config()
    assert cfg.get("embed_thumbnail") == CONFIG_DEFAULTS["embed_thumbnail"]


# ---------------------------------------------------------------------------
# Migration: unknown key is ignored (forward compatibility)
# ---------------------------------------------------------------------------


def test_config_unknown_key_is_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keys present in the file but absent from CONFIG_DEFAULTS are discarded."""
    monkeypatch.setenv("YTDLPGUI_CONFIG_DIR", str(tmp_path))

    data = dict(CONFIG_DEFAULTS)
    data["future_option_xyz"] = "some_value"  # type: ignore[assignment]
    _config_file(tmp_path).write_text(json.dumps(data), encoding="utf-8")

    cfg = Config()
    # The unknown key must not be stored.
    assert cfg.get("future_option_xyz") is None


# ---------------------------------------------------------------------------
# Corrupt file falls back silently
# ---------------------------------------------------------------------------


def test_config_corrupt_file_uses_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A corrupt JSON file is ignored; Config falls back to defaults."""
    monkeypatch.setenv("YTDLPGUI_CONFIG_DIR", str(tmp_path))
    _config_file(tmp_path).write_text("NOT VALID JSON {{{{", encoding="utf-8")

    cfg = Config()
    assert cfg.get("audio_format") == CONFIG_DEFAULTS["audio_format"]


# ---------------------------------------------------------------------------
# video_dir / audio_dir helpers
# ---------------------------------------------------------------------------


def test_video_dir_and_audio_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """video_dir and audio_dir return base_dir / subfolder as Path."""
    monkeypatch.setenv("YTDLPGUI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.set("base_dir", str(tmp_path / "downloads"))
    cfg.set("video_subfolder", "vids")
    cfg.set("audio_subfolder", "audio")

    assert cfg.video_dir() == tmp_path / "downloads" / "vids"
    assert cfg.audio_dir() == tmp_path / "downloads" / "audio"


# ---------------------------------------------------------------------------
# as_download_options
# ---------------------------------------------------------------------------


def test_as_download_options_url_and_mode(tmp_config: Config) -> None:
    """as_download_options correctly passes url and mode."""
    opts = tmp_config.as_download_options("https://example.com/v", DownloadMode.AUDIO)
    assert opts.url == "https://example.com/v"
    assert opts.mode == DownloadMode.AUDIO


def test_as_download_options_cookie_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """cookies_source is applied only when the cookie module is enabled."""
    monkeypatch.setenv("YTDLPGUI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.set("cookies_source", CookieSource.BROWSER.value)

    # Disabled (default) → NONE, even if a source is configured.
    assert cfg.as_download_options("https://example.com/v").cookie_source == CookieSource.NONE

    # Enabled → the configured source is used.
    cfg.set("cookies_enabled", True)
    assert cfg.as_download_options("https://example.com/v").cookie_source == CookieSource.BROWSER


def test_as_download_options_subtitle_langs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Subtitle languages are read from config."""
    monkeypatch.setenv("YTDLPGUI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.set("subtitle_langs", ["de", "fr"])
    opts = cfg.as_download_options("https://example.com/v")
    assert opts.subtitle_langs == ["de", "fr"]


def test_as_download_options_format_id_override(tmp_config: Config) -> None:
    """Caller-supplied format_id is forwarded unchanged."""
    opts = tmp_config.as_download_options("https://example.com/v", format_id="137")
    assert opts.format_id == "137"
