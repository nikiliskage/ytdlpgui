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
        "This video is age-restricted — it needs sign-in cookies.",
    ),
    (
        # YouTube's bot check; same remedy as age restriction (sign-in cookies).
        re.compile(r"Sign in to confirm you.?re not a bot", re.IGNORECASE),
        ErrorKind.AGE_RESTRICTED,
        "The site wants to confirm you're not a bot — it needs sign-in cookies.",
    ),
    (
        # Members-only: fetchable with cookies for a member account.
        re.compile(r"members-only|members only|join this channel", re.IGNORECASE),
        ErrorKind.AGE_RESTRICTED,
        "This is members-only content — it needs sign-in cookies for a member account.",
    ),
    (
        re.compile(r"Requested format is not available", re.IGNORECASE),
        ErrorKind.FORMAT_UNAVAILABLE,
        "That format isn't available for this video. Pick another quality/format, or use Best.",
    ),
    (
        re.compile(r"Private video", re.IGNORECASE),
        ErrorKind.UNAVAILABLE,
        "This video is private — you need an account that's been granted access.",
    ),
    (
        re.compile(r"has not made this video available in your country", re.IGNORECASE),
        ErrorKind.UNAVAILABLE,
        "This video is blocked in your country (geo-restricted).",
    ),
    (
        re.compile(r"This live event will begin|Premieres in|Premiere will begin", re.IGNORECASE),
        ErrorKind.UNAVAILABLE,
        "This is a scheduled live stream / premiere that hasn't started yet.",
    ),
    (
        re.compile(r"Video unavailable", re.IGNORECASE),
        ErrorKind.UNAVAILABLE,
        "This video is unavailable (removed, or it never existed).",
    ),
    (
        re.compile(r"(ffmpeg|ffprobe).*(not found|not installed|Aborting)", re.IGNORECASE),
        ErrorKind.FFMPEG_MISSING,
        "ffmpeg wasn't found. Set its path in Settings → Binaries (needed to merge video + audio).",
    ),
    (
        # Rate limiting — must precede the generic "HTTP Error \\d+" network rule.
        re.compile(r"HTTP Error 429|Too Many Requests", re.IGNORECASE),
        ErrorKind.NETWORK,
        "The site is rate-limiting you (HTTP 429). Wait a few minutes — or sign in with "
        "cookies — then retry.",
    ),
    (
        re.compile(
            r"(HTTP Error \d+|urlopen error|getaddrinfo|connection (timed out|refused)|"
            r"Unable to connect|Network is unreachable|timed? out)",
            re.IGNORECASE,
        ),
        ErrorKind.NETWORK,
        "Network problem — check your connection and retry.",
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

    # Unknown: surface yt-dlp's own ERROR line so the failure is diagnosable,
    # instead of a generic "something went wrong".
    return AppError(
        kind=ErrorKind.UNKNOWN,
        user_message=_extract_error_line(text) or "An unexpected error occurred.",
        raw=text,
    )


def _extract_error_line(text: str) -> str:
    """Pull the most relevant yt-dlp error line out of stderr, cleaned up."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    chosen = next((line for line in reversed(lines) if "ERROR" in line.upper()), lines[-1])
    # Drop the "ERROR:" prefix and any "[extractor] <id>:" prefix.
    chosen = re.sub(r"^ERROR:\s*", "", chosen, flags=re.IGNORECASE)
    chosen = re.sub(r"^\[[^\]]+\]\s+[^:]+:\s*", "", chosen)
    return chosen[:197] + "..." if len(chosen) > 200 else chosen
