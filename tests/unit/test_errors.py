"""Unit tests for app.core.errors.map_stderr().

Uses the stderr fixture samples defined in tests/fixtures/stderr_samples.py.
"""

from __future__ import annotations

import pytest
from app.core.contracts import PO_TOKEN_HELP_URL, ErrorKind
from app.core.errors import map_stderr
from tests.fixtures.stderr_samples import AGE_RESTRICTED, EXPECTED


@pytest.mark.parametrize("text,expected_kind", list(EXPECTED.items()))
def test_map_stderr_kind(text: str, expected_kind: str) -> None:
    """map_stderr maps each sample to the expected ErrorKind value."""
    error = map_stderr(text)
    assert error.kind.value == expected_kind, (
        f"Expected kind={expected_kind!r}, got {error.kind.value!r}\nInput: {text!r}"
    )


def test_age_restricted_has_hint_url() -> None:
    """AGE_RESTRICTED errors include the PO token help URL as hint_url."""
    error = map_stderr(AGE_RESTRICTED)
    assert error.kind == ErrorKind.AGE_RESTRICTED
    assert error.hint_url == PO_TOKEN_HELP_URL


def test_age_restricted_raw_preserved() -> None:
    """raw field contains the original stderr text."""
    error = map_stderr(AGE_RESTRICTED)
    assert AGE_RESTRICTED in error.raw


def test_unknown_has_no_hint_url() -> None:
    """Non-age-restricted errors do not have a hint URL."""
    error = map_stderr("ERROR: something unexpected")
    assert error.hint_url is None


def test_empty_string_returns_unknown() -> None:
    """Empty input yields UNKNOWN kind."""
    error = map_stderr("")
    assert error.kind == ErrorKind.UNKNOWN


def test_unknown_surfaces_cleaned_error_line() -> None:
    """UNKNOWN errors expose yt-dlp's own ERROR line (prefixes stripped)."""
    text = (
        "[youtube] dQw4w9WgXcQ: Downloading webpage\n"
        "ERROR: [youtube] dQw4w9WgXcQ: Unable to download subtitles for 'ar'"
    )
    error = map_stderr(text)
    assert error.kind == ErrorKind.UNKNOWN
    assert error.user_message == "Unable to download subtitles for 'ar'"
    assert text in error.raw


def test_map_stderr_is_pure() -> None:
    """Calling map_stderr twice with the same input returns equal results."""
    text = "ERROR: HTTP Error 403: Forbidden"
    r1 = map_stderr(text)
    r2 = map_stderr(text)
    assert r1.kind == r2.kind
    assert r1.user_message == r2.user_message
