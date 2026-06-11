"""yt-dlp process runner (QProcess-based, implements IYtDlpRunner).

Stream B — runner layer.

Architecture notes
------------------
* ``parse_progress_line`` is a **pure function** — easily unit-tested without
  any Qt event loop.
* ``YtDlpRunner`` maintains a stdout line-buffer so chunks split mid-line are
  handled correctly (a common QProcess pitfall).
* ``no_window_kwargs`` is imported lazily at runtime (inside methods) so that
  this module can be imported even when Stream A (paths.py) is not yet present.
"""

from __future__ import annotations

import shutil

from app.core.contracts import (
    AppError,
    DownloadOptions,
    FinishedCallback,
    JobState,
    LogCallback,
    Progress,
    ProgressCallback,
)
from app.core.errors import map_stderr

try:
    from PySide6.QtCore import QObject, QProcess, Signal

    _QT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QT_AVAILABLE = False
    QObject = object  # type: ignore[misc,assignment]

# ---------------------------------------------------------------------------
# Pure helper: parse a single PROG| line
# ---------------------------------------------------------------------------

_NA_VALUES = {"NA", "None", "none", "", "N/A"}


def _parse_float(value: str) -> float | None:
    if value in _NA_VALUES:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_int(value: str) -> int | None:
    f = _parse_float(value)
    if f is None:
        return None
    return int(f)


def parse_progress_line(line: str) -> Progress | None:
    """Parse a yt-dlp ``--progress-template`` line into a :class:`Progress`.

    Expected format::

        PROG|status|downloaded_bytes|total_bytes|total_bytes_estimate|speed|eta

    Returns ``None`` for lines that are not progress lines.
    Pure function — no side effects.
    """
    line = line.strip()
    if not line.startswith("PROG|"):
        return None

    parts = line.split("|")
    if len(parts) < 7:
        return None

    # parts[0] = "PROG"
    status = parts[1].strip() or "downloading"
    downloaded_bytes = _parse_int(parts[2])
    total_raw = parts[3].strip()
    total_est_raw = parts[4].strip()
    speed = _parse_float(parts[5])
    eta = _parse_int(parts[6])

    # Resolve total_bytes: prefer actual, fall back to estimate.
    total_bytes: int | None
    if total_raw not in _NA_VALUES:
        total_bytes = _parse_int(total_raw)
    elif total_est_raw not in _NA_VALUES:
        total_bytes = _parse_int(total_est_raw)
    else:
        total_bytes = None

    indeterminate = total_bytes is None

    return Progress(
        status=status,
        downloaded_bytes=downloaded_bytes,
        total_bytes=total_bytes,
        speed=speed,
        eta=eta,
        indeterminate=indeterminate,
    )


# ---------------------------------------------------------------------------
# Line buffer helper (pure logic, extracted for unit-testing)
# ---------------------------------------------------------------------------


class LineBuffer:
    """Accumulate stdout chunks and yield complete lines.

    Handles the common case where a QProcess ``readyReadStandardOutput``
    chunk arrives mid-line.
    """

    def __init__(self) -> None:
        self._buf: str = ""

    def feed(self, chunk: str) -> list[str]:
        """Feed a chunk of text; return any newly completed lines."""
        self._buf += chunk
        lines: list[str] = []
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            lines.append(line)
        return lines

    def flush(self) -> list[str]:
        """Return (and clear) any remaining partial line."""
        remaining = self._buf
        self._buf = ""
        if remaining:
            return [remaining]
        return []


# ---------------------------------------------------------------------------
# YtDlpRunner — QObject wrapper around QProcess
# ---------------------------------------------------------------------------


class YtDlpRunner(QObject):
    """Single-job yt-dlp runner backed by QProcess.

    Implements :class:`~app.core.contracts.IYtDlpRunner`.

    Usage::

        runner = YtDlpRunner()
        runner.set_callbacks(on_progress, on_log, on_finished)
        runner.start(options)
        # ... later ...
        runner.cancel()

    Signals are emitted through the callbacks registered with
    :meth:`set_callbacks`; Qt signals (``progress``, ``log``,
    ``finished``) are defined on the class for direct Qt connections.
    """

    if _QT_AVAILABLE:
        progress: Signal = Signal(Progress)
        log: Signal = Signal(str)
        finished_signal: Signal = Signal(JobState, object)  # object = AppError | None

    def __init__(self, parent: QObject | None = None) -> None:
        if _QT_AVAILABLE:
            super().__init__(parent)
        else:
            super().__init__()

        self._on_progress: ProgressCallback | None = None
        self._on_log: LogCallback | None = None
        self._on_finished: FinishedCallback | None = None

        self._process: QProcess | None = None
        self._stderr_buf: str = ""
        self._line_buffer: LineBuffer = LineBuffer()

    # ------------------------------------------------------------------
    # IYtDlpRunner interface
    # ------------------------------------------------------------------

    def set_callbacks(
        self,
        on_progress: ProgressCallback,
        on_log: LogCallback,
        on_finished: FinishedCallback,
    ) -> None:
        """Register observer callbacks."""
        self._on_progress = on_progress
        self._on_log = on_log
        self._on_finished = on_finished

    def start(self, options: DownloadOptions) -> None:
        """Build args and launch yt-dlp via QProcess."""
        from app.core.command_builder import build_command

        ytdlp_path = self._locate_ytdlp()
        ffmpeg_path = self._locate_ffmpeg()
        args = build_command(options, ytdlp_path=ytdlp_path, ffmpeg_path=ffmpeg_path)

        # Lazily import no_window_kwargs from Stream A (may not exist yet).
        try:
            from app.core.paths import no_window_kwargs

            no_window_kwargs()
        except Exception:
            pass

        self._line_buffer = LineBuffer()
        self._stderr_buf = ""

        if not _QT_AVAILABLE:  # pragma: no cover
            return

        process = QProcess(self)
        self._process = process

        process.readyReadStandardOutput.connect(self._on_stdout)
        process.readyReadStandardError.connect(self._on_stderr_ready)
        process.finished.connect(self._on_process_finished)

        program = args[0]
        arguments = args[1:]
        process.start(program, arguments)

    def cancel(self) -> None:
        """Terminate the running process (.part file is preserved)."""
        if self._process is not None and _QT_AVAILABLE:
            self._process.terminate()
            # Do NOT call waitForFinished here; _on_process_finished will fire.

    # ------------------------------------------------------------------
    # QProcess slots
    # ------------------------------------------------------------------

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        raw = bytes(self._process.readAllStandardOutput().data()).decode("utf-8", errors="replace")
        for line in self._line_buffer.feed(raw):
            self._dispatch_line(line)

    def _on_stderr_ready(self) -> None:
        if self._process is None:
            return
        raw = bytes(self._process.readAllStandardError().data()).decode("utf-8", errors="replace")
        self._stderr_buf += raw
        if self._on_log:
            for line in raw.splitlines():
                self._on_log(line)

    def _on_process_finished(self, exit_code: int, exit_status: object) -> None:
        # Flush any partial line still in the buffer.
        for line in self._line_buffer.flush():
            self._dispatch_line(line)

        if exit_code == 0:
            state = JobState.COMPLETED
            error: AppError | None = None
        else:
            state = JobState.FAILED
            error = map_stderr(self._stderr_buf)

        if self._on_finished:
            self._on_finished(state, error)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _dispatch_line(self, line: str) -> None:
        prog = parse_progress_line(line)
        if prog is not None:
            if self._on_progress:
                self._on_progress(prog)
        else:
            if line.strip() and self._on_log:
                self._on_log(line)

    @staticmethod
    def _locate_ytdlp() -> str:
        """Find yt-dlp on PATH or return the bare name."""
        try:
            from app.core.paths import resolve_ytdlp

            result = resolve_ytdlp()
            if result.found and result.path:
                return str(result.path)
        except Exception:
            pass
        found = shutil.which("yt-dlp")
        return found if found else "yt-dlp"

    @staticmethod
    def _locate_ffmpeg() -> str:
        """Find ffmpeg on PATH or return empty string (let yt-dlp auto-detect)."""
        try:
            from app.core.paths import resolve_ffmpeg

            result = resolve_ffmpeg()
            if result.found and result.path:
                return str(result.path)
        except Exception:
            pass
        found = shutil.which("ffmpeg")
        return found if found else ""
