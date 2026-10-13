"""Subtitle-language parsing from yt-dlp -J output (pure helpers)."""

from __future__ import annotations

import json

from app.core.contracts import AppError, FormatInfo, MediaInfo, PlaylistInfo
from app.core.format_fetcher import (
    FormatFetcher,
    _lang_keys,
    _parse_media_info,
    _parse_playlist_info,
    _parse_playlist_items,
)

# ---------------------------------------------------------------------------
# Fetch argument composition (cookies applied at fetch time)
# ---------------------------------------------------------------------------


def test_build_fetch_args_without_cookies() -> None:
    args = FormatFetcher._build_fetch_args("https://x/v", [])
    assert args == ["-J", "--flat-playlist", "--no-playlist", "--", "https://x/v"]


def test_build_fetch_args_includes_cookies_before_url() -> None:
    args = FormatFetcher._build_fetch_args("https://x/v", ["--cookies", "c.txt"])
    assert args == [
        "-J",
        "--flat-playlist",
        "--no-playlist",
        "--cookies",
        "c.txt",
        "--",
        "https://x/v",
    ]


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


# ---------------------------------------------------------------------------
# Playlists
# ---------------------------------------------------------------------------


def test_parse_playlist_info_from_flat_dump(sample_flat: dict) -> None:  # type: ignore[type-arg]
    info = _parse_playlist_info(sample_flat)
    assert info.id == "PL1234567890"
    assert info.title == "Sample Playlist"
    assert [i.index for i in info.items] == [1, 2, 3]
    assert info.items[1].url == "https://www.youtube.com/watch?v=vid0000002"


def test_parse_playlist_items_prefers_playlist_index_and_skips_urlless() -> None:
    data: dict[str, object] = {
        "entries": [
            {"id": "a", "title": "A", "url": "https://x/a", "playlist_index": 5, "duration": 61},
            {"id": "gone", "title": "[Deleted video]"},  # no URL → can't download
            None,
            {"id": "c", "url": "https://x/c"},
        ]
    }
    items = _parse_playlist_items(data)
    assert [(i.id, i.index) for i in items] == [("a", 5), ("c", 4)]
    assert items[0].duration == 61
    assert items[1].title == "c"  # falls back to the id


def test_handle_dump_playlist_goes_to_on_playlist(sample_flat: dict) -> None:  # type: ignore[type-arg]
    fetcher = FormatFetcher()
    playlists: list[PlaylistInfo] = []
    done: list[object] = []
    fetcher._handle_dump(
        json.dumps(sample_flat), "", lambda m, f: done.append(m), lambda e: None, playlists.append
    )
    assert not done
    assert len(playlists) == 1 and len(playlists[0].items) == 3


def test_handle_dump_playlist_without_handler_is_an_error(sample_flat: dict) -> None:  # type: ignore[type-arg]
    fetcher = FormatFetcher()
    errors: list[AppError] = []
    fetcher._handle_dump(json.dumps(sample_flat), "", lambda m, f: None, errors.append)
    assert len(errors) == 1 and "playlist" in errors[0].user_message
