"""yt-dlp argument builder (Builder pattern, pure — no side effects).

Stream B — command construction layer.

Usage::

    args = (
        YtDlpCommandBuilder()
        .base("yt-dlp", "ffmpeg")
        .common(opts.concurrent_fragments)
        .output(opts.video_dir, opts.output_template)
        .format_video(opts.format_id, opts.preset)
        .subtitles(opts.subtitle_langs, opts.write_auto_subs, opts.embed_subs)
        .embed_extras(opts.embed_thumbnail, opts.embed_metadata)
        .cookies(opts.cookie_source, opts.browser, opts.cookies_file)
        .build(opts.url)
    )
"""

from __future__ import annotations

from pathlib import Path

from app.core.contracts import (
    PRESET_480P,
    PRESET_720P,
    PRESET_1080P,
    PRESET_BEST,
    CookieSource,
    DownloadMode,
    DownloadOptions,
)

# --progress-template emitted by yt-dlp (PROG| prefix for easy detection).
_PROGRESS_TEMPLATE = (
    "PROG|%(progress.status)s"
    "|%(progress.downloaded_bytes)s"
    "|%(progress.total_bytes)s"
    "|%(progress.total_bytes_estimate)s"
    "|%(progress.speed)s"
    "|%(progress.eta)s"
)


def _video_selector(cap: str = "") -> str:
    """Format selector preferring AAC (m4a) audio so the merged mp4 stays playable.

    YouTube's plain ``bestaudio`` is usually Opus, and Opus inside an mp4
    container plays silently in many players. We try an m4a (AAC) audio stream
    first, then fall back to whatever audio is best, then to a single combined
    format. ``cap`` is an optional height filter like ``[height<=1080]``.
    """
    return f"bestvideo{cap}+bestaudio[ext=m4a]/bestvideo{cap}+bestaudio/best{cap}"


# Logical preset → yt-dlp format selector
_PRESET_FORMAT: dict[str, str] = {
    PRESET_BEST: _video_selector(),
    PRESET_1080P: _video_selector("[height<=1080]"),
    PRESET_720P: _video_selector("[height<=720]"),
    PRESET_480P: _video_selector("[height<=480]"),
}


class YtDlpCommandBuilder:
    """Chainable builder that accumulates yt-dlp CLI arguments.

    All methods return ``self`` for chaining.  Call :meth:`build` last.
    """

    def __init__(self) -> None:
        self._args: list[str] = []
        self._ytdlp: str = "yt-dlp"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add(self, *args: str) -> YtDlpCommandBuilder:
        self._args.extend(args)
        return self

    # ------------------------------------------------------------------
    # Chainable configuration methods
    # ------------------------------------------------------------------

    def base(self, ytdlp_path: str, ffmpeg_path: str = "") -> YtDlpCommandBuilder:
        """Set yt-dlp executable path and optional ffmpeg location."""
        self._ytdlp = ytdlp_path
        if ffmpeg_path:
            self._add("--ffmpeg-location", ffmpeg_path)
        return self

    def common(self, concurrent_fragments: int = 4) -> YtDlpCommandBuilder:
        """Add flags shared across all download modes."""
        # Only ever download the single video the user selected. Without this, a
        # URL that carries a playlist (e.g. ...&list=WL from "Watch Later") makes
        # yt-dlp download the whole list. The fetch step already uses
        # --no-playlist; the download must match (playlist support is deferred).
        self._add("--no-playlist")
        self._add("--windows-filenames")
        self._add("--continue")
        self._add("--concurrent-fragments", str(concurrent_fragments))
        self._add("--newline")
        self._add("--progress-template", _PROGRESS_TEMPLATE)
        return self

    def output(self, directory: Path, template: str) -> YtDlpCommandBuilder:
        """Set output path template."""
        output_path = str(directory / template)
        self._add("-o", output_path)
        return self

    def format_video(
        self,
        format_id: str | None,
        preset: str | None,
    ) -> YtDlpCommandBuilder:
        """Add video format selector and merge-output args."""
        if format_id:
            selector = format_id
        else:
            selector = _PRESET_FORMAT.get(preset or PRESET_BEST, _PRESET_FORMAT[PRESET_BEST])
        self._add("-f", selector)
        self._add("--merge-output-format", "mp4")
        return self

    def format_audio(self, audio_format: str) -> YtDlpCommandBuilder:
        """Add audio extraction args.

        An empty/``best``/``bestaudio`` format keeps the source codec: yt-dlp
        extracts the original audio stream with no lossy re-encode (fast,
        lossless). Any concrete format (opus/mp3/m4a) converts to it.
        """
        self._add("-x")
        if audio_format and audio_format not in ("best", "bestaudio"):
            self._add("--audio-format", audio_format)
            self._add("--audio-quality", "0")
        return self

    def subtitles(
        self,
        langs: list[str],
        write_auto: bool = False,
        embed: bool = False,
    ) -> YtDlpCommandBuilder:
        """Add subtitle args alongside a media download (video mode)."""
        self._add("--write-subs")
        self._add("--sub-langs", ",".join(langs))
        if write_auto:
            self._add("--write-auto-subs")
        if embed:
            self._add("--embed-subs")
        return self

    def subtitles_only(self, langs: list[str]) -> YtDlpCommandBuilder:
        """Subtitle-only download: write just the manual subtitle, skip the media."""
        self._add("--skip-download")
        self._add("--write-subs")
        self._add("--sub-langs", ",".join(langs))
        return self

    def embed_extras(
        self,
        thumbnail: bool = False,
        metadata: bool = False,
    ) -> YtDlpCommandBuilder:
        """Conditionally add --embed-thumbnail / --embed-metadata."""
        if thumbnail:
            self._add("--embed-thumbnail")
        if metadata:
            self._add("--embed-metadata")
        return self

    def cookies(
        self,
        source: CookieSource,
        browser: str | None = None,
        cookies_file: Path | None = None,
    ) -> YtDlpCommandBuilder:
        """Add cookie args based on CookieSource."""
        if source == CookieSource.BROWSER and browser:
            self._add("--cookies-from-browser", browser)
        elif source == CookieSource.FILE and cookies_file:
            self._add("--cookies", str(cookies_file))
        return self

    # ------------------------------------------------------------------
    # Terminal: assemble the full command
    # ------------------------------------------------------------------

    def build(self, url: str) -> list[str]:
        """Return the complete yt-dlp command as a list of strings."""
        return [self._ytdlp, *self._args, "--", url]


# ---------------------------------------------------------------------------
# Convenience factory: build a full command from a DownloadOptions object.
# ---------------------------------------------------------------------------


def build_command(
    options: DownloadOptions,
    ytdlp_path: str = "yt-dlp",
    ffmpeg_path: str = "",
) -> list[str]:
    """Build the yt-dlp command list for *options*.

    This is a thin wrapper around :class:`YtDlpCommandBuilder` that maps
    all fields of ``DownloadOptions`` to builder calls.
    """
    builder = YtDlpCommandBuilder()
    builder.base(ytdlp_path, ffmpeg_path)
    builder.common(options.concurrent_fragments)

    if options.mode == DownloadMode.AUDIO:
        builder.output(options.audio_dir, options.output_template)
        builder.format_audio(options.audio_format)
    elif options.mode == DownloadMode.SUBTITLE:
        # Subtitle-only: skip the media, write just the manual subtitle file
        # (embedding is irrelevant with no media file).
        builder.output(options.video_dir, options.output_template)
        builder.subtitles_only(options.subtitle_langs)
    else:
        # VIDEO (default)
        builder.output(options.video_dir, options.output_template)
        builder.format_video(options.format_id, options.preset)

    # Subtitle flags for video mode (embed/write alongside video).
    if options.mode == DownloadMode.VIDEO:
        if options.subtitle_langs and (options.write_auto_subs or options.embed_subs):
            builder.subtitles(
                options.subtitle_langs,
                options.write_auto_subs,
                options.embed_subs,
            )

    # Thumbnail/metadata embedding needs a media file; skip it for subtitle-only.
    if options.mode != DownloadMode.SUBTITLE:
        builder.embed_extras(options.embed_thumbnail, options.embed_metadata)
    builder.cookies(options.cookie_source, options.browser, options.cookies_file)

    return builder.build(options.url)
