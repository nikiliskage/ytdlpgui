"""Subtitle-language parsing from yt-dlp -J output (pure helpers)."""

from __future__ import annotations

from app.core.format_fetcher import _lang_keys, _parse_media_info


def test_lang_keys_sorted_from_dict() -> None:
    assert _lang_keys({"tr": [{}], "en": [{}]}) == ["en", "tr"]


def test_lang_keys_non_dict_is_empty() -> None:
    assert _lang_keys(None) == []
    assert _lang_keys([]) == []


def test_parse_media_info_captures_subtitle_langs() -> None:
    data: dict[str, object] = {
        "title": "Clip",
        "subtitles": {"en": [{}], "tr": [{}]},
        "automatic_captions": {"de": [{}], "fr": [{}]},
    }
    media = _parse_media_info(data)
    assert media.subtitle_langs == ["en", "tr"]
    assert media.auto_caption_langs == ["de", "fr"]


def test_parse_media_info_without_subtitles() -> None:
    media = _parse_media_info({"title": "Clip"})
    assert media.subtitle_langs == []
    assert media.auto_caption_langs == []
