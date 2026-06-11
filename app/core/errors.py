"""stderr → AppError mapping (pure function, no side effects).

Stream B — errors layer.
"""

from __future__ import annotations

import re

from app.core.contracts import PO_TOKEN_HELP_URL, AppError, ErrorKind

# ---------------------------------------------------------------------------
# Pattern table: (compiled regex, ErrorKind, user_message)
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[re.Pattern[str], ErrorKind, str]] = [
    (
        re.compile(r"Sign in to confirm your age", re.IGNORECASE),
        ErrorKind.AGE_RESTRICTED,
        "This video requires age verification. Sign in or provide cookies.",
    ),
    (
        re.compile(r"Requested format is not available", re.IGNORECASE),
        ErrorKind.FORMAT_UNAVAILABLE,
        "The requested format is not available for this video.",
    ),
    (
        re.compile(r"Private video", re.IGNORECASE),
        ErrorKind.UNAVAILABLE,
        "This video is private.",
    ),
    (
        re.compile(r"Video unavailable", re.IGNORECASE),
        ErrorKind.UNAVAILABLE,
        "This video is unavailable.",
    ),
    (
        re.compile(r"has not made this video available in your country", re.IGNORECASE),
        ErrorKind.UNAVAILABLE,
        "This video is not available in your country (geo-blocked).",
    ),
    (
        re.compile(r"(ffmpeg|ffprobe).*(not found|not installed|Aborting)", re.IGNORECASE),
        ErrorKind.FFMPEG_MISSING,
        "ffmpeg/ffprobe is not installed or not found. Please install ffmpeg.",
    ),
    (
        re.compile(
            r"(HTTP Error \d+|urlopen error|getaddrinfo|connection (timed out|refused)|"
            r"Unable to connect|Network is unreachable|timed? out)",
            re.IGNORECASE,
        ),
        ErrorKind.NETWORK,
        "A network error occurred. Check your connection and try again.",
    ),
]


def map_stderr(text: str) -> AppError:
    """Map yt-dlp stderr output to a typed AppError.

    Pure function — reads ``text``, returns an ``AppError``, no side effects.
    """
    for pattern, kind, message in _PATTERNS:
        if pattern.search(text):
            hint = PO_TOKEN_HELP_URL if kind == ErrorKind.AGE_RESTRICTED else None
            return AppError(
                kind=kind,
                user_message=message,
                raw=text,
                hint_url=hint,
            )

    # Unknown: include last few raw lines as context.
    last_lines = "\n".join(line for line in text.splitlines()[-5:] if line.strip())
    return AppError(
        kind=ErrorKind.UNKNOWN,
        user_message="An unexpected error occurred.",
        raw=text if text else last_lines,
    )
