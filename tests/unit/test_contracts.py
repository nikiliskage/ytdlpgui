"""Faz 0 sözleşmelerinin birim testleri (saf; PySide6 gerektirmez)."""

from __future__ import annotations

from pathlib import Path

from app.core import contracts as c


def test_progress_percent_normal() -> None:
    p = c.Progress(downloaded_bytes=50, total_bytes=200)
    assert p.percent == 25.0


def test_progress_percent_indeterminate_when_no_total() -> None:
    assert c.Progress(downloaded_bytes=50, total_bytes=None).percent is None
    assert c.Progress(indeterminate=True, downloaded_bytes=50, total_bytes=200).percent is None


def test_progress_percent_capped_at_100() -> None:
    p = c.Progress(downloaded_bytes=250, total_bytes=200)
    assert p.percent == 100.0


def test_jobstate_terminal() -> None:
    assert c.JobState.COMPLETED.is_terminal
    assert c.JobState.FAILED.is_terminal
    assert c.JobState.CANCELED.is_terminal
    assert not c.JobState.QUEUED.is_terminal
    assert not c.JobState.RUNNING.is_terminal


def test_download_options_target_dir() -> None:
    opts = c.DownloadOptions(url="x", video_dir=Path("V"), audio_dir=Path("M"))
    opts.mode = c.DownloadMode.VIDEO
    assert opts.target_dir() == Path("V")
    opts.mode = c.DownloadMode.AUDIO
    assert opts.target_dir() == Path("M")


def test_download_options_defaults() -> None:
    opts = c.DownloadOptions(url="x")
    assert opts.subtitle_langs == ["en", "tr"]
    assert opts.audio_format == "opus"
    assert opts.concurrent_fragments == 4


def test_media_info_defaults() -> None:
    m = c.MediaInfo(title="t")
    assert m.needs_cookies is False
    assert m.duration is None


def test_binary_status_has_version_field() -> None:
    assert c.BinaryStatus(found=False).version is None


def test_runner_factory_alias_callable() -> None:
    # RunnerFactory bir Callable alias'ı; çağrılabilir tip olmalı.
    assert c.RunnerFactory is not None


def test_config_defaults_complete() -> None:
    d = c.CONFIG_DEFAULTS
    assert d["max_concurrent_downloads"] == 2
    assert d["audio_format"] == "opus"
    assert d["subtitle_langs"] == ["en", "tr"]
    assert d["accent_theme"] == "purple"
    assert d["dock_style"] == "ring"
    assert d["reduced_motion"] is False


def test_presets_exist() -> None:
    assert {c.PRESET_BEST, c.PRESET_1080P, c.PRESET_720P, c.PRESET_480P, c.PRESET_AUDIO} == {
        "best",
        "1080p",
        "720p",
        "480p",
        "audio",
    }
