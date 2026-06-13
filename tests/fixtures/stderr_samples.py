"""Gerçek yt-dlp stderr örnekleri → beklenen ErrorKind.

Stream B `errors.map_stderr()` testleri bunu kullanır. `EXPECTED`, her örnek
metni `app.core.contracts.ErrorKind` değerinin (string) adına eşler.
"""

AGE_RESTRICTED = (
    "ERROR: [youtube] dQw4w9WgXcQ: Sign in to confirm your age. "
    "This video may be inappropriate for some users."
)

FORMAT_UNAVAILABLE = (
    "ERROR: [youtube] dQw4w9WgXcQ: Requested format is not available. "
    "Use --list-formats for a list of available formats"
)

PRIVATE_VIDEO = (
    "ERROR: [youtube] abcdEFGHijk: Private video. "
    "Sign in if you've been granted access to this video"
)

VIDEO_UNAVAILABLE = (
    "ERROR: [youtube] abcdEFGHijk: Video unavailable. This video is no longer available"
)

GEO_BLOCKED = (
    "ERROR: [youtube] abcdEFGHijk: The uploader has not made this video available in your country"
)

FFMPEG_MISSING = (
    "ERROR: You have requested merging of multiple formats but ffmpeg is not installed. "
    "Aborting due to --abort-on-error"
)

NETWORK_TIMEOUT = (
    "ERROR: unable to download video data: <urlopen error [Errno 11001] getaddrinfo failed>"
)

HTTP_403 = "ERROR: unable to download video data: HTTP Error 403: Forbidden"

RATE_LIMITED_429 = "ERROR: unable to download video data: HTTP Error 429: Too Many Requests"

MEMBERS_ONLY = (
    "ERROR: [youtube] abcdEFGHijk: Join this channel to get access to members-only content"
)

LIVE_NOT_STARTED = "ERROR: [youtube] abcdEFGHijk: This live event will begin in 2 hours."

BOT_CHECK = (
    "ERROR: [youtube] abcdEFGHijk: Sign in to confirm you're not a bot. "
    "Use --cookies-from-browser or --cookies for the authentication."
)

UNKNOWN = "ERROR: [generic] Something completely unexpected happened in extractor"

#: örnek metin → beklenen ErrorKind.value
EXPECTED: dict[str, str] = {
    AGE_RESTRICTED: "age_restricted",
    BOT_CHECK: "age_restricted",
    MEMBERS_ONLY: "age_restricted",
    FORMAT_UNAVAILABLE: "format_unavailable",
    PRIVATE_VIDEO: "unavailable",
    VIDEO_UNAVAILABLE: "unavailable",
    GEO_BLOCKED: "unavailable",
    LIVE_NOT_STARTED: "unavailable",
    FFMPEG_MISSING: "ffmpeg_missing",
    NETWORK_TIMEOUT: "network",
    HTTP_403: "network",
    RATE_LIMITED_429: "network",
    UNKNOWN: "unknown",
}
