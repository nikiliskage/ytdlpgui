"""Format / metadata / playlist fetcher (async via QProcess).

Stream B — metadata layer.

Implements :class:`~app.core.contracts.IFormatFetcher`.

yt-dlp is located on every fetch from the injected config (Settings ->
Binaries), so a path change takes effect without a restart.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from app.core.contracts import (
    AppError,
    ErrorKind,
    FormatInfo,
    IConfig,
    MediaInfo,
    PlaylistInfo,
    PlaylistItem,
)
from app.core.errors import map_stderr
from app.core.paths import YTDLP_NOT_FOUND_MESSAGE, find_ytdlp

try:
    from PySide6.QtCore import QObject, QProcess, QTimer

    _QT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QT_AVAILABLE = False
    QObject = object  # type: ignore[misc,assignment]

# How long a metadata fetch may run before we give up (ms). yt-dlp normally
# answers in a few seconds; a much longer run means it is stuck (slow site,
# blocked, or waiting on something) and the UI would otherwise spin forever.
_FETCH_TIMEOUT_MS = 90_000


# ---------------------------------------------------------------------------
# JSON → dataclass helpers (pure)
# ---------------------------------------------------------------------------


def _to_int(value: object) -> int | None:
    """Coerce a JSON value to int, or None if not convertible."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, (float, str)):
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def _to_float(value: object) -> float | None:
    """Coerce a JSON value to float, or None if not convertible."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _parse_media_info(data: dict[str, object]) -> MediaInfo:
    """Extract :class:`MediaInfo` fields from ``yt-dlp -J`` output."""
    age_limit = _to_int(data.get("age_limit")) or 0
    availability = str(data.get("availability") or "public")
    needs_cookies = age_limit >= 18 or availability not in ("public", "unlisted", "")
    return MediaInfo(
        title=str(data.get("title") or ""),
        channel=str(data.get("channel") or data.get("uploader") or ""),
        duration=_to_int(data.get("duration")),
        thumbnail_url=str(data.get("thumbnail") or ""),
        webpage_url=str(data.get("webpage_url") or ""),
        needs_cookies=needs_cookies,
        subtitle_langs=_lang_keys(data.get("subtitles")),
    )


def _lang_keys(value: object) -> list[str]:
    """Sorted language codes from a yt-dlp ``subtitles`` dict."""
    if isinstance(value, dict):
        return sorted(str(k) for k in value)
    return []


def _parse_format_list(data: dict[str, object]) -> list[FormatInfo]:
    """Extract :class:`FormatInfo` items from ``yt-dlp -J`` output."""
    raw_formats_val = data.get("formats")
    raw_formats: list[object] = list(raw_formats_val) if isinstance(raw_formats_val, list) else []
    result: list[FormatInfo] = []
    for fmt_raw in raw_formats:
        if not isinstance(fmt_raw, dict):
            continue
        fmt: dict[str, object] = fmt_raw
        filesize = _to_int(fmt.get("filesize"))
        if filesize is None:
            filesize = _to_int(fmt.get("filesize_approx"))

        fps = _to_float(fmt.get("fps"))
        tbr = _to_float(fmt.get("tbr"))

        resolution = str(fmt.get("resolution") or "")
        if not resolution:
            w = fmt.get("width")
            h = fmt.get("height")
            if w and h:
                resolution = f"{w}x{h}"

        vcodec_val = fmt.get("vcodec")
        acodec_val = fmt.get("acodec")
        result.append(
            FormatInfo(
                format_id=str(fmt.get("format_id") or ""),
                ext=str(fmt.get("ext") or ""),
                resolution=resolution,
                fps=fps,
                vcodec=str(vcodec_val) if vcodec_val not in (None, "none") else None,
                acodec=str(acodec_val) if acodec_val not in (None, "none") else None,
                filesize=filesize,
                tbr=tbr,
                note=str(fmt.get("format_note") or ""),
            )
        )
    return result


def _parse_playlist_items(data: dict[str, object]) -> list[PlaylistItem]:
    """Extract :class:`PlaylistItem` list from ``yt-dlp --flat-playlist -J``.

    ``index`` is the entry's position in the playlist (``playlist_index`` when
    yt-dlp reports it, else its 1-based order). Entries without a URL are
    skipped — they can't be downloaded (e.g. deleted/private videos).
    """
    entries_val = data.get("entries")
    entries: list[object] = list(entries_val) if isinstance(entries_val, list) else []
    result: list[PlaylistItem] = []
    for position, entry_raw in enumerate(entries, start=1):
        if not isinstance(entry_raw, dict):
            continue
        entry: dict[str, object] = entry_raw
        url = str(entry.get("url") or entry.get("webpage_url") or "")
        if not url:
            continue
        result.append(
            PlaylistItem(
                id=str(entry.get("id") or ""),
                title=str(entry.get("title") or entry.get("id") or url),
                url=url,
                index=_to_int(entry.get("playlist_index")) or position,
                duration=_to_int(entry.get("duration")),
            )
        )
    return result


def _parse_playlist_info(data: dict[str, object]) -> PlaylistInfo:
    """Extract :class:`PlaylistInfo` (title + items) from a playlist ``-J`` dump."""
    playlist_id = str(data.get("id") or "")
    return PlaylistInfo(
        id=playlist_id,
        title=str(data.get("title") or playlist_id or "Playlist"),
        items=_parse_playlist_items(data),
    )


def _is_playlist(data: dict[str, object]) -> bool:
    """True if a ``-J`` dump describes a playlist rather than a single video."""
    return data.get("_type") in ("playlist", "multi_video")


# ---------------------------------------------------------------------------
# FormatFetcher — QObject
# ---------------------------------------------------------------------------


class FormatFetcher(QObject):
    """Fetch format metadata and expand playlists via yt-dlp subprocess.

    Implements :class:`~app.core.contracts.IFormatFetcher`.
    """

    def __init__(self, config: IConfig | None = None, parent: QObject | None = None) -> None:
        if _QT_AVAILABLE:
            super().__init__(parent)
        else:
            super().__init__()

        self._config = config
        # Current in-flight subprocess state (one fetch at a time). Each _run
        # bumps the generation; callbacks from an older run are ignored.
        self._process: QProcess | None = None
        self._timer: QTimer | None = None
        self._generation: int = 0

    # ------------------------------------------------------------------
    # IFormatFetcher interface
    # ------------------------------------------------------------------

    @staticmethod
    def _build_fetch_args(url: str, cookie_args: list[str]) -> list[str]:
        """Compose the ``yt-dlp -J`` argument list (pure, unit-testable).

        Cookie args are included so age-restricted / sign-in videos can be read
        at fetch time — not just at download time.

        ``--flat-playlist`` only affects playlist URLs: a single video is still
        fully extracted, while a pure playlist link returns its entry list
        quickly instead of resolving every video (handled via ``on_playlist``).
        ``--no-playlist`` keeps a ``watch?v=…&list=…`` link on the one video.
        """
        return ["-J", "--flat-playlist", "--no-playlist", *cookie_args, "--", url]

    def _cookie_args(self) -> list[str]:
        """Cookie CLI flags from the injected config (empty if none/unavailable)."""
        getter = getattr(self._config, "cookie_cli_args", None)
        if callable(getter):
            try:
                result = getter()
            except Exception:
                return []
            if isinstance(result, list):
                return [str(a) for a in result]
        return []

    def fetch_formats(
        self,
        url: str,
        on_done: Callable[[MediaInfo, list[FormatInfo]], None],
        on_error: Callable[[AppError], None],
        on_playlist: Callable[[PlaylistInfo], None] | None = None,
    ) -> None:
        """Run ``yt-dlp -J --no-playlist`` (with cookies) and parse the result."""
        args = self._build_fetch_args(url, self._cookie_args())
        self._run(
            args,
            lambda stdout, stderr: self._handle_dump(
                stdout, stderr, on_done, on_error, on_playlist
            ),
        )

    def expand_playlist(
        self,
        url: str,
        on_done: Callable[[PlaylistInfo], None],
        on_error: Callable[[AppError], None],
    ) -> None:
        """Run ``yt-dlp --flat-playlist -J`` (with cookies) and parse the result."""
        args = ["--flat-playlist", "-J", *self._cookie_args(), "--", url]
        self._run(
            args,
            lambda stdout, stderr: self._handle_flat(stdout, stderr, on_done, on_error),
        )

    # ------------------------------------------------------------------
    # Subprocess helpers
    # ------------------------------------------------------------------

    def cancel(self) -> None:
        """Cancel the in-flight fetch (if any). Suppresses its callback.

        The UI resets itself on cancel; we just stop the subprocess/timer and
        make sure the pending ``on_finish`` never fires.
        """
        self._generation += 1
        self._stop_current()

    def _stop_current(self) -> None:
        """Stop the in-flight subprocess/timer (its callbacks are already stale)."""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self._process is not None and _QT_AVAILABLE:
            self._process.kill()
            self._process = None

    def _run(
        self,
        extra_args: list[str],
        on_finish: Callable[[str, str], None],
    ) -> None:
        """Launch yt-dlp and invoke *on_finish* with (stdout, stderr) exactly once.

        Guards against the UI spinning forever: a timeout kills a stuck process,
        and ``errorOccurred`` (e.g. the binary can't start) is reported instead
        of being silently dropped.
        """
        if not _QT_AVAILABLE:  # pragma: no cover
            return

        # A new fetch supersedes any in-flight one: stop it and invalidate its
        # callbacks so a late result can never be delivered as this fetch's.
        self._generation += 1
        generation = self._generation
        self._stop_current()

        process = QProcess(self)
        self._process = process
        stdout_buf: list[str] = []
        stderr_buf: list[str] = []

        timer = QTimer(self)
        timer.setSingleShot(True)
        self._timer = timer

        def _finish_once(stdout: str, stderr: str) -> None:
            if generation != self._generation:
                return
            self._generation += 1  # deliver at most once
            timer.stop()
            on_finish(stdout, stderr)

        def _read_out() -> None:
            raw = bytes(process.readAllStandardOutput().data()).decode("utf-8", errors="replace")
            stdout_buf.append(raw)

        def _read_err() -> None:
            raw = bytes(process.readAllStandardError().data()).decode("utf-8", errors="replace")
            stderr_buf.append(raw)

        def _finished(_exit_code: int, _exit_status: object) -> None:
            _finish_once("".join(stdout_buf), "".join(stderr_buf))

        def _error(err: object) -> None:
            # FailedToStart = the binary path is wrong/missing; report it clearly.
            # Other errors (e.g. Crashed from our own kill()) are handled by the
            # timeout/cancel/finished paths, so ignore them here.
            if err == QProcess.ProcessError.FailedToStart:
                _finish_once(
                    "",
                    "ERROR: yt-dlp could not be started. Check its path in Settings → Binaries.",
                )

        def _timeout() -> None:
            if generation != self._generation:
                return
            process.kill()
            _finish_once(
                "",
                "ERROR: Fetch timed out. The site may be slow or blocked, "
                "or the video may need cookies (Settings → Cookies).",
            )

        ytdlp = self._locate_ytdlp()
        if ytdlp is None:
            # Never fall back to a bare "yt-dlp" (QProcess would search PATH).
            message = f"ERROR: {YTDLP_NOT_FOUND_MESSAGE}"
            QTimer.singleShot(0, self, lambda: _finish_once("", message))
            return

        timer.timeout.connect(_timeout)
        process.readyReadStandardOutput.connect(_read_out)
        process.readyReadStandardError.connect(_read_err)
        process.finished.connect(_finished)
        process.errorOccurred.connect(_error)
        process.start(ytdlp, extra_args)
        timer.start(_FETCH_TIMEOUT_MS)

    # ------------------------------------------------------------------
    # Parse callbacks
    # ------------------------------------------------------------------

    def _handle_dump(
        self,
        stdout: str,
        stderr: str,
        on_done: Callable[[MediaInfo, list[FormatInfo]], None],
        on_error: Callable[[AppError], None],
        on_playlist: Callable[[PlaylistInfo], None] | None = None,
    ) -> None:
        if not stdout.strip():
            on_error(map_stderr(stderr))
            return
        try:
            parsed: object = json.loads(stdout)
        except json.JSONDecodeError as exc:
            on_error(
                AppError(
                    kind=ErrorKind.UNKNOWN,
                    user_message=f"Failed to parse yt-dlp output: {exc}",
                    raw=stdout[:500],
                )
            )
            return
        # yt-dlp can exit 0 yet emit ``null`` (or a non-object) for a URL it can't
        # resolve to a single video — surface the real reason from stderr instead
        # of crashing on ``None.get(...)``.
        if not isinstance(parsed, dict):
            error = map_stderr(stderr) if stderr.strip() else None
            on_error(
                error
                or AppError(
                    kind=ErrorKind.UNAVAILABLE,
                    user_message="Couldn't read this video's info. Check the link and try again.",
                    raw=stdout[:500],
                )
            )
            return
        if _is_playlist(parsed):
            if on_playlist is not None:
                on_playlist(_parse_playlist_info(parsed))
            else:
                on_error(
                    AppError(
                        kind=ErrorKind.UNAVAILABLE,
                        user_message="This link is a playlist, not a single video.",
                    )
                )
            return
        try:
            media = _parse_media_info(parsed)
            formats = _parse_format_list(parsed)
            on_done(media, formats)
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            on_error(
                AppError(
                    kind=ErrorKind.UNKNOWN,
                    user_message=f"Failed to parse yt-dlp output: {exc}",
                    raw=stdout[:500],
                )
            )

    def _handle_flat(
        self,
        stdout: str,
        stderr: str,
        on_done: Callable[[PlaylistInfo], None],
        on_error: Callable[[AppError], None],
    ) -> None:
        if not stdout.strip():
            on_error(map_stderr(stderr))
            return
        try:
            data: object = json.loads(stdout)
            if not isinstance(data, dict):
                on_error(map_stderr(stderr))
                return
            on_done(_parse_playlist_info(data))
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            on_error(
                AppError(
                    kind=ErrorKind.UNKNOWN,
                    user_message=f"Failed to parse playlist output: {exc}",
                    raw=stdout[:500],
                )
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _locate_ytdlp(self) -> str | None:
        """Configured path, else the app's install folder; None if neither has it."""
        configured = ""
        if self._config is not None:
            try:
                configured = str(self._config.get("ytdlp_path") or "")
            except Exception:
                configured = ""
        found = find_ytdlp(configured)
        return str(found) if found else None
