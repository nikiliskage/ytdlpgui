"""Subtitle-language parsing from yt-dlp -J output (pure helpers)."""

from __future__ import annotations

from app.core.contracts import AppError, FormatInfo, MediaInfo
from app.core.format_fetcher import FormatFetcher, _lang_keys, _parse_media_info

# ---------------------------------------------------------------------------
# Fetch argument composition (cookies applied at fetch time)
# ---------------------------------------------------------------------------


def test_build_fetch_args_without_cookies() -> None:
    args = FormatFetcher._build_fetch_args("https://x/v", [])
    assert args == ["-J", "--no-playlist", "--", "https://x/v"]


def test_build_fetch_args_includes_cookies_before_url() -> None:
    args = FormatFetcher._build_fetch_args("https://x/v", ["--cookies", "c.txt"])
    assert args == ["-J", "--no-playlist", "--cookies", "c.txt", "--", "https://x/v"]


# ---------------------------------------------------------------------------
# _handle_dump robustness — yt-dlp can exit 0 yet print "null"
# ---------------------------------------------------------------------------


def test_handle_dump_null_stdout_reports_error_without_crashing() -> None:
    """A JSON ``null`` body must surface an error, not raise AttributeError."""
    fetcher = FormatFetcher()
    done: list[tuple[MediaInfo, list[FormatInfo]]] = []
    errors: list[AppError] = []
    fetcher._handle_dump(
        "null",
        "ERROR: Video unavailable",
        lambda media, fmts: done.append((media, fmts)),
        errors.append,
    )
    assert not done
    assert len(errors) == 1


def test_handle_dump_valid_json_calls_done() -> None:
    fetcher = FormatFetcher()
    done: list[tuple[MediaInfo, list[FormatInfo]]] = []
    fetcher._handle_dump(
        '{"title": "Clip", "formats": []}',
        "",
        lambda media, fmts: done.append((media, fmts)),
        lambda err: None,
    )
    assert len(done) == 1
    assert done[0][0].title == "Clip"


def test_lang_keys_sorted_from_dict() -> None:
    assert _lang_keys({"tr": [{}], "en": [{}]}) == ["en", "tr"]


def test_lang_keys_non_dict_is_empty() -> None:
    assert _lang_keys(None) == []
    assert _lang_keys([]) == []


def test_parse_media_info_captures_manual_subtitle_langs() -> None:
    data: dict[str, object] = {
        "title": "Clip",
        "subtitles": {"en": [{}], "tr": [{}]},
        "automatic_captions": {"de": [{}], "fr": [{}]},  # ignored — manual only
    }
    media = _parse_media_info(data)
    assert media.subtitle_langs == ["en", "tr"]


def test_parse_media_info_without_subtitles() -> None:
    media = _parse_media_info({"title": "Clip"})
    assert media.subtitle_langs == []
