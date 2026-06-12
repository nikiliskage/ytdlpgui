"""Pure helpers in app.ui_state (subtitle language matching)."""

from __future__ import annotations

from app.ui_state import match_subtitle_code


def test_exact_match_returned() -> None:
    assert match_subtitle_code("en", ["en", "tr"]) == "en"


def test_region_variant_matched() -> None:
    assert match_subtitle_code("de", ["en", "de-DE"]) == "de-DE"


def test_prefers_exact_over_variant() -> None:
    assert match_subtitle_code("en", ["en-US", "en"]) == "en"


def test_no_match_returns_none() -> None:
    assert match_subtitle_code("fr", ["en", "de-DE"]) is None
