"""Format / metadata / playlist fetcher (async via QProcess).

Stream B — metadata layer.

Implements :class:`~app.core.contracts.IFormatFetcher`.

``no_window_kwargs`` is imported lazily so the module loads even when
Stream A (paths.py) has not been written yet.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable

from app.core.contracts import (
    AppError,
    ErrorKind,
    FormatInfo,
    IConfig,
    MediaInfo,
    PlaylistItem,
)
from app.core.errors import map_stderr

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
    """Extract :class:`PlaylistItem` list from ``yt-dlp --flat-playlist -J``."""
    entries_val = data.get("entries")
    entries: list[object] = list(entries_val) if isinstance(entries_val, list) else []
    result: list[PlaylistItem] = []
    for entry_raw in entries:
        if not isinstance(entry_raw, dict):
            continue
        entry: dict[str, object] = entry_raw
        url = str(entry.get("url") or entry.get("webpage_url") or "")
        result.append(
            PlaylistItem(
                id=str(entry.get("id") or ""),
                title=str(entry.get("title") or ""),
                url=url,
            )
        )
    return result


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
        self._ytdlp: str = self._locate_ytdlp()
        # Current in-flight subprocess state (one fetch at a time).
        self._process: QProcess | None = None
        self._timer: QTimer | None = None
        self._done: bool = False
        self._canceled: bool = False

    # ------------------------------------------------------------------
    # IFormatFetcher interface
    # ------------------------------------------------------------------

    @staticmethod
    def _build_fetch_args(url: str, cookie_args: list[str]) -> list[str]:
        """Compose the ``yt-dlp -J`` argument list (pure, unit-testable).

        Cookie args are included so age-restricted / sign-in videos can be read
        at fetch time — not just at download time.
        """
        return ["-J", "--no-playlist", *cookie_args, "--", url]

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
    ) -> None:
        """Run ``yt-dlp -J --no-playlist`` (with cookies) and parse the result."""
        args = self._build_fetch_args(url, self._cookie_args())
        self._run(
            args,
            lambda stdout, stderr: self._handle_dump(stdout, stderr, on_done, on_error),
        )

    def expand_playlist(
        self,
        url: str,
        on_done: Callable[[list[PlaylistItem]], None],
        on_error: Callable[[AppError], None],
    ) -> None:
        """Run ``yt-dlp --flat-playlist -J`` and parse the result."""
        args = ["--flat-playlist", "-J", "--", url]
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
        self._canceled = True
        if self._timer is not None:
            self._timer.stop()
        if self._process is not None and _QT_AVAILABLE:
            self._process.kill()

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

        # Lazily import no_window_kwargs (Stream A may be absent).
        # Called for its side-effect of preparing the subprocess environment.
        try:
            from app.core.paths import no_window_kwargs

            no_window_kwargs()
        except Exception:
            pass

        process = QProcess(self)
        self._process = process
        self._done = False
        self._canceled = False
        stdout_buf: list[str] = []
        stderr_buf: list[str] = []

        timer = QTimer(self)
        timer.setSingleShot(True)
        self._timer = timer

        def _finish_once(stdout: str, stderr: str) -> None:
            if self._done or self._canceled:
                return
            self._done = True
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
            if self._done or self._canceled:
                return
            process.kill()
            _finish_once(
                "",
                "ERROR: Fetch timed out. The site may be slow or blocked, "
                "or the video may need cookies (Settings → Cookies).",
            )

        timer.timeout.connect(_timeout)
        process.readyReadStandardOutput.connect(_read_out)
        process.readyReadStandardError.connect(_read_err)
        process.finished.connect(_finished)
        process.errorOccurred.connect(_error)
        process.start(self._ytdlp, extra_args)
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
        on_done: Callable[[list[PlaylistItem]], None],
        on_error: Callable[[AppError], None],
    ) -> None:
        if not stdout.strip():
            on_error(map_stderr(stderr))
            return
        try:
            data: dict[str, object] = json.loads(stdout)
            items = _parse_playlist_items(data)
            on_done(items)
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

    @staticmethod
    def _locate_ytdlp() -> str:
        try:
            from app.core.paths import resolve_ytdlp

            result = resolve_ytdlp()
            if result.found and result.path:
                return str(result.path)
        except Exception:
            pass
        found = shutil.which("yt-dlp")
        return found if found else "yt-dlp"
