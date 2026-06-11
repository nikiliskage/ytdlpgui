"""Unit tests for parse_progress_line() and LineBuffer.

Covers:
- CASES: normal, estimate-only, indeterminate, finished
- NON_PROGRESS_LINES: → None
- SPLIT_CHUNKS: line-buffer assembles a split chunk into one Progress
"""

from __future__ import annotations

import pytest
from app.core.ytdlp_runner import LineBuffer, parse_progress_line
from tests.fixtures.progress_lines import CASES, NON_PROGRESS_LINES, SPLIT_CHUNKS

# ---------------------------------------------------------------------------
# parse_progress_line — CASES
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("line,expected", CASES)
def test_parse_progress_line_cases(line: str, expected: dict[str, object]) -> None:
    """parse_progress_line correctly parses every fixture CASE."""
    result = parse_progress_line(line)
    assert result is not None, f"Expected a Progress but got None for: {line!r}"
    for field_name, expected_value in expected.items():
        actual = getattr(result, field_name)
        assert actual == expected_value, (
            f"Field {field_name!r}: expected {expected_value!r}, got {actual!r}\nLine: {line!r}"
        )


# ---------------------------------------------------------------------------
# parse_progress_line — NON_PROGRESS_LINES
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("line", NON_PROGRESS_LINES)
def test_parse_progress_line_non_progress(line: str) -> None:
    """Non-PROG lines return None."""
    assert parse_progress_line(line) is None, f"Expected None for: {line!r}"


# ---------------------------------------------------------------------------
# LineBuffer — SPLIT_CHUNKS
# ---------------------------------------------------------------------------


def test_line_buffer_split_chunks() -> None:
    """A progress line split across two chunks is assembled correctly."""
    buf = LineBuffer()

    # Feed first chunk (incomplete — no newline).
    lines_after_first = buf.feed(SPLIT_CHUNKS[0])
    assert lines_after_first == [], "No complete line yet after first chunk"

    # Feed second chunk (completes the line with a trailing newline).
    lines_after_second = buf.feed(SPLIT_CHUNKS[1])
    assert len(lines_after_second) == 1, (
        f"Expected exactly one complete line, got: {lines_after_second!r}"
    )

    full_line = lines_after_second[0]
    result = parse_progress_line(full_line)
    assert result is not None, f"Expected Progress from reassembled line: {full_line!r}"
    assert result.downloaded_bytes == 1048576
    assert result.total_bytes == 10485760
    assert result.speed == 524288.0
    assert result.eta == 18
    assert result.indeterminate is False


def test_line_buffer_no_newline_held() -> None:
    """Incomplete line (no trailing newline) is held in buffer until flush."""
    buf = LineBuffer()
    lines = buf.feed("PROG|downloading|1234|NA|NA|NA|NA")
    assert lines == []
    flushed = buf.flush()
    assert len(flushed) == 1
    result = parse_progress_line(flushed[0])
    assert result is not None
    assert result.downloaded_bytes == 1234
    assert result.indeterminate is True


def test_line_buffer_multiple_lines() -> None:
    """Multiple newline-terminated lines in one chunk are all returned."""
    buf = LineBuffer()
    chunk = "PROG|downloading|100|1000|1000|50.0|18\nPROG|downloading|200|1000|1000|50.0|16\n"
    lines = buf.feed(chunk)
    assert len(lines) == 2
    for line in lines:
        assert parse_progress_line(line) is not None


def test_parse_progress_indeterminate_fields() -> None:
    """When both total and estimate are NA, total_bytes is None and indeterminate=True."""
    line = "PROG|downloading|3145728|NA|NA|450000.0|NA"
    result = parse_progress_line(line)
    assert result is not None
    assert result.total_bytes is None
    assert result.indeterminate is True
    assert result.eta is None
    assert result.downloaded_bytes == 3145728


def test_parse_progress_estimate_fallback() -> None:
    """When total is NA but estimate is present, estimate becomes total_bytes."""
    line = "PROG|downloading|2097152|NA|10485760|600000.0|14"
    result = parse_progress_line(line)
    assert result is not None
    assert result.total_bytes == 10485760
    assert result.indeterminate is False
