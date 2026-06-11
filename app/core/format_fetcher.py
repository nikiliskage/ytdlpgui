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
    MediaInfo,
    PlaylistItem,
)
from app.core.errors import map_stderr

try:
    from PySide6.QtCore import QObject, QProcess

    _QT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QT_AVAILABLE = False
    QObject = object  # type: ignore[misc,assignment]


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
    )


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

    def __init__(self, parent: QObject | None = None) -> None:
        if _QT_AVAILABLE:
            super().__init__(parent)
        else:
            super().__init__()

        self._ytdlp: str = self._locate_ytdlp()

    # ------------------------------------------------------------------
    # IFormatFetcher interface
    # ------------------------------------------------------------------

    def fetch_formats(
        self,
        url: str,
        on_done: Callable[[MediaInfo, list[FormatInfo]], None],
        on_error: Callable[[AppError], None],
    ) -> None:
        """Run ``yt-dlp -J --no-playlist`` and parse the result."""
        args = ["-J", "--no-playlist", "--", url]
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

    def _run(
        self,
        extra_args: list[str],
        on_finish: Callable[[str, str], None],
    ) -> None:
        """Launch yt-dlp and invoke *on_finish* with (stdout, stderr)."""
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
        stdout_buf: list[str] = []
        stderr_buf: list[str] = []

        def _read_out() -> None:
            raw = bytes(process.readAllStandardOutput().data()).decode("utf-8", errors="replace")
            stdout_buf.append(raw)

        def _read_err() -> None:
            raw = bytes(process.readAllStandardError().data()).decode("utf-8", errors="replace")
            stderr_buf.append(raw)

        def _finished(_exit_code: int, _exit_status: object) -> None:
            on_finish("".join(stdout_buf), "".join(stderr_buf))

        process.readyReadStandardOutput.connect(_read_out)
        process.readyReadStandardError.connect(_read_err)
        process.finished.connect(_finished)
        process.start(self._ytdlp, extra_args)

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
            data: dict[str, object] = json.loads(stdout)
            media = _parse_media_info(data)
            formats = _parse_format_list(data)
            on_done(media, formats)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
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
