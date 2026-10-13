"""Pure helpers in app.ui_state (subtitle language matching)."""

from __future__ import annotations

from app.ui_state import format_duration, match_subtitle_code, playlist_url


def test_exact_match_returned() -> None:
    assert match_subtitle_code("en", ["en", "tr"]) == "en"


def test_region_variant_matched() -> None:
    assert match_subtitle_code("de", ["en", "de-DE"]) == "de-DE"


def test_prefers_exact_over_variant() -> None:
    assert match_subtitle_code("en", ["en-US", "en"]) == "en"


def test_no_match_returns_none() -> None:
    assert match_subtitle_code("fr", ["en", "de-DE"]) is None


# ---------------------------------------------------------------------------
# playlist_url / format_duration
# ---------------------------------------------------------------------------


def test_playlist_url_from_mixed_watch_link() -> None:
    url = "https://www.youtube.com/watch?v=abc&list=PL123&index=4"
    assert playlist_url(url) == "https://www.youtube.com/playlist?list=PL123"


def test_playlist_url_short_link() -> None:
    assert playlist_url("https://youtu.be/abc?list=PL9") == (
        "https://www.youtube.com/playlist?list=PL9"
    )


def test_playlist_url_none_without_list_or_off_youtube() -> None:
    assert playlist_url("https://www.youtube.com/watch?v=abc") is None
    assert playlist_url("https://vimeo.com/123?list=PL1") is None
    assert playlist_url("not a url") is None
    # Auto-generated mixes are not real playlists.
    assert playlist_url("https://www.youtube.com/watch?v=abc&list=RDabc") is None


def test_format_duration() -> None:
    assert format_duration(None) == "—"
    assert format_duration(65) == "1:05"
    assert format_duration(3725) == "1:02:05"
