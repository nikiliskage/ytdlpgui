"""Unit tests for app.core.command_builder.

Parametrized over all modes, presets, and flag combinations.
Pure function — no Qt or subprocess involved.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.command_builder import YtDlpCommandBuilder, build_command
from app.core.contracts import (
    PRESET_480P,
    PRESET_720P,
    PRESET_1080P,
    PRESET_BEST,
    CookieSource,
    DownloadMode,
    DownloadOptions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_opts(**kwargs: object) -> DownloadOptions:
    """Create DownloadOptions with sensible path defaults + overrides."""
    defaults: dict[str, object] = {
        "url": "https://example.com/watch?v=test",
        "video_dir": Path("C:/videos"),
        "audio_dir": Path("C:/musics"),
        "output_template": "%(title)s.%(ext)s",
    }
    defaults.update(kwargs)
    return DownloadOptions(**defaults)


def _args(opts: DownloadOptions, **kw: str) -> list[str]:
    ytdlp = kw.get("ytdlp", "yt-dlp")
    ffmpeg = kw.get("ffmpeg", "")
    return build_command(opts, ytdlp_path=ytdlp, ffmpeg_path=ffmpeg)


# ---------------------------------------------------------------------------
# Common flags (present in every mode)
# ---------------------------------------------------------------------------


def test_common_flags_present_video() -> None:
    opts = _make_opts()
    args = _args(opts)
    assert "--no-playlist" in args  # never grab a whole playlist (e.g. ...&list=WL)
    assert "--windows-filenames" in args
    assert "--continue" in args
    assert "--newline" in args
    assert "--concurrent-fragments" in args
    assert "4" in args  # default value


def test_concurrent_fragments_custom() -> None:
    opts = _make_opts(concurrent_fragments=8)
    args = _args(opts)
    idx = args.index("--concurrent-fragments")
    assert args[idx + 1] == "8"


def test_progress_template_present() -> None:
    opts = _make_opts()
    args = _args(opts)
    assert "--progress-template" in args
    idx = args.index("--progress-template")
    assert args[idx + 1].startswith("PROG|")


def test_url_appended_last_with_separator() -> None:
    """URL comes after '--' end-of-options separator."""
    opts = _make_opts(url="https://example.com/v=abc")
    args = _args(opts)
    assert args[-1] == "https://example.com/v=abc"
    assert "--" in args
    assert args.index("--") == len(args) - 2


def test_ffmpeg_location_added_when_provided() -> None:
    opts = _make_opts()
    args = build_command(opts, ytdlp_path="yt-dlp", ffmpeg_path="C:/ffmpeg/ffmpeg.exe")
    assert "--ffmpeg-location" in args
    idx = args.index("--ffmpeg-location")
    assert args[idx + 1] == "C:/ffmpeg/ffmpeg.exe"


def test_ffmpeg_location_omitted_when_empty() -> None:
    opts = _make_opts()
    args = _args(opts)
    assert "--ffmpeg-location" not in args


# ---------------------------------------------------------------------------
# Video mode
# ---------------------------------------------------------------------------


class TestVideoMode:
    def test_output_template_video_dir(self) -> None:
        opts = _make_opts(mode=DownloadMode.VIDEO)
        args = _args(opts)
        idx = args.index("-o")
        assert "C:/videos" in args[idx + 1] or "C:\\videos" in args[idx + 1]

    def test_merge_output_format_mp4(self) -> None:
        opts = _make_opts(mode=DownloadMode.VIDEO)
        args = _args(opts)
        assert "--merge-output-format" in args
        idx = args.index("--merge-output-format")
        assert args[idx + 1] == "mp4"

    def test_no_x_flag_in_video_mode(self) -> None:
        opts = _make_opts(mode=DownloadMode.VIDEO)
        args = _args(opts)
        assert "-x" not in args

    @pytest.mark.parametrize(
        "preset,expected_fragment",
        [
            (PRESET_BEST, "bestvideo+bestaudio/best"),
            (PRESET_1080P, "height<=1080"),
            (PRESET_720P, "height<=720"),
            (PRESET_480P, "height<=480"),
        ],
    )
    def test_preset_format_selector(self, preset: str, expected_fragment: str) -> None:
        opts = _make_opts(mode=DownloadMode.VIDEO, preset=preset, format_id=None)
        args = _args(opts)
        idx = args.index("-f")
        selector = args[idx + 1]
        assert expected_fragment in selector, (
            f"Preset {preset!r}: expected {expected_fragment!r} in {selector!r}"
        )

    def test_explicit_format_id_overrides_preset(self) -> None:
        opts = _make_opts(mode=DownloadMode.VIDEO, format_id="137+140", preset=PRESET_BEST)
        args = _args(opts)
        idx = args.index("-f")
        assert args[idx + 1] == "137+140"


# ---------------------------------------------------------------------------
# Audio mode
# ---------------------------------------------------------------------------


class TestAudioMode:
    def test_x_flag_present(self) -> None:
        opts = _make_opts(mode=DownloadMode.AUDIO)
        args = _args(opts)
        assert "-x" in args

    def test_audio_format_flag(self) -> None:
        opts = _make_opts(mode=DownloadMode.AUDIO, audio_format="mp3")
        args = _args(opts)
        assert "--audio-format" in args
        idx = args.index("--audio-format")
        assert args[idx + 1] == "mp3"

    @pytest.mark.parametrize("native", ["", "best", "bestaudio"])
    def test_best_audio_keeps_native_codec(self, native: str) -> None:
        """'Best audio' extracts the source codec without a lossy re-encode."""
        opts = _make_opts(mode=DownloadMode.AUDIO, audio_format=native)
        args = _args(opts)
        assert "-x" in args
        assert "--audio-format" not in args
        assert "--audio-quality" not in args

    def test_audio_quality_zero(self) -> None:
        opts = _make_opts(mode=DownloadMode.AUDIO)
        args = _args(opts)
        assert "--audio-quality" in args
        idx = args.index("--audio-quality")
        assert args[idx + 1] == "0"

    def test_output_uses_audio_dir(self) -> None:
        opts = _make_opts(mode=DownloadMode.AUDIO)
        args = _args(opts)
        idx = args.index("-o")
        assert "C:/musics" in args[idx + 1] or "C:\\musics" in args[idx + 1]

    def test_no_merge_format_in_audio_mode(self) -> None:
        opts = _make_opts(mode=DownloadMode.AUDIO)
        args = _args(opts)
        assert "--merge-output-format" not in args

    def test_no_f_flag_in_audio_mode(self) -> None:
        opts = _make_opts(mode=DownloadMode.AUDIO)
        args = _args(opts)
        assert "-f" not in args


# ---------------------------------------------------------------------------
# Subtitle mode
# ---------------------------------------------------------------------------


class TestSubtitleMode:
    def test_write_subs_flag(self) -> None:
        opts = _make_opts(mode=DownloadMode.SUBTITLE, subtitle_langs=["en", "tr"])
        args = _args(opts)
        assert "--write-subs" in args

    def test_sub_langs_flag(self) -> None:
        opts = _make_opts(mode=DownloadMode.SUBTITLE, subtitle_langs=["en", "tr"])
        args = _args(opts)
        assert "--sub-langs" in args
        idx = args.index("--sub-langs")
        assert "en" in args[idx + 1]
        assert "tr" in args[idx + 1]

    def test_no_video_format_in_subtitle_mode(self) -> None:
        opts = _make_opts(mode=DownloadMode.SUBTITLE)
        args = _args(opts)
        assert "-f" not in args
        assert "--merge-output-format" not in args

    def test_no_x_flag_in_subtitle_mode(self) -> None:
        opts = _make_opts(mode=DownloadMode.SUBTITLE)
        args = _args(opts)
        assert "-x" not in args

    def test_subtitle_only_skips_media_download(self) -> None:
        opts = _make_opts(mode=DownloadMode.SUBTITLE)
        assert "--skip-download" in _args(opts)

    def test_subtitle_only_uses_manual_write_subs(self) -> None:
        # Manual subtitles only — auto-translations are rate-limited by YouTube.
        opts = _make_opts(mode=DownloadMode.SUBTITLE, write_auto_subs=True)
        args = _args(opts)
        assert "--write-subs" in args
        assert "--write-auto-subs" not in args

    def test_subtitle_only_ignores_embed(self) -> None:
        # With no media file there is nothing to embed into.
        opts = _make_opts(
            mode=DownloadMode.SUBTITLE,
            embed_subs=True,
            embed_thumbnail=True,
            embed_metadata=True,
        )
        args = _args(opts)
        assert "--embed-subs" not in args
        assert "--embed-thumbnail" not in args
        assert "--embed-metadata" not in args


# ---------------------------------------------------------------------------
# Embed extras
# ---------------------------------------------------------------------------


class TestEmbedExtras:
    def test_embed_thumbnail_flag(self) -> None:
        opts_on = _make_opts(embed_thumbnail=True)
        opts_off = _make_opts(embed_thumbnail=False)
        assert "--embed-thumbnail" in _args(opts_on)
        assert "--embed-thumbnail" not in _args(opts_off)

    def test_embed_metadata_flag(self) -> None:
        opts_on = _make_opts(embed_metadata=True)
        opts_off = _make_opts(embed_metadata=False)
        assert "--embed-metadata" in _args(opts_on)
        assert "--embed-metadata" not in _args(opts_off)


# ---------------------------------------------------------------------------
# Cookies
# ---------------------------------------------------------------------------


class TestCookies:
    def test_no_cookie_args_when_source_none(self) -> None:
        opts = _make_opts(cookie_source=CookieSource.NONE)
        args = _args(opts)
        assert "--cookies-from-browser" not in args
        assert "--cookies" not in args

    def test_browser_cookie_source(self) -> None:
        opts = _make_opts(cookie_source=CookieSource.BROWSER, browser="chrome")
        args = _args(opts)
        assert "--cookies-from-browser" in args
        idx = args.index("--cookies-from-browser")
        assert args[idx + 1] == "chrome"

    def test_file_cookie_source(self) -> None:
        opts = _make_opts(
            cookie_source=CookieSource.FILE,
            cookies_file=Path("C:/cookies.txt"),
        )
        args = _args(opts)
        assert "--cookies" in args
        idx = args.index("--cookies")
        assert "cookies.txt" in args[idx + 1]

    def test_browser_source_without_browser_value_no_flag(self) -> None:
        """If CookieSource.BROWSER but browser is None, flag is omitted."""
        opts = _make_opts(cookie_source=CookieSource.BROWSER, browser=None)
        args = _args(opts)
        assert "--cookies-from-browser" not in args

    def test_file_source_without_path_no_flag(self) -> None:
        """If CookieSource.FILE but cookies_file is None, flag is omitted."""
        opts = _make_opts(cookie_source=CookieSource.FILE, cookies_file=None)
        args = _args(opts)
        assert "--cookies" not in args


# ---------------------------------------------------------------------------
# Builder chaining API (direct usage)
# ---------------------------------------------------------------------------


class TestBuilderAPI:
    def test_build_returns_list_of_strings(self) -> None:
        args = YtDlpCommandBuilder().common().build("https://example.com/v=1")
        assert isinstance(args, list)
        assert all(isinstance(a, str) for a in args)

    def test_builder_is_chainable(self) -> None:
        builder = YtDlpCommandBuilder()
        result = builder.common().embed_extras(thumbnail=True).cookies(CookieSource.NONE)
        assert result is builder  # same instance returned

    def test_builder_program_at_index_zero(self) -> None:
        args = YtDlpCommandBuilder().base("my-yt-dlp").build("https://x.com")
        assert args[0] == "my-yt-dlp"

    def test_subtitles_langs_joined_with_comma(self) -> None:
        builder = YtDlpCommandBuilder()
        builder.subtitles(["en", "fr", "de"])
        args = builder.build("https://x.com")
        idx = args.index("--sub-langs")
        assert args[idx + 1] == "en,fr,de"
