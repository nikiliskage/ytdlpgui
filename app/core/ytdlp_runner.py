"""yt-dlp process runner (QProcess-based, implements IYtDlpRunner).

Stream B — runner layer.

Architecture notes
------------------
* ``parse_progress_line`` is a **pure function** — easily unit-tested without
  any Qt event loop.
* ``YtDlpRunner`` maintains a stdout line-buffer so chunks split mid-line are
  handled correctly (a common QProcess pitfall).
* Binaries are located per ``start()`` from the injected config (Settings ->
  Binaries), without running them: no blocking ``--version`` on the GUI thread.
"""

from __future__ import annotations

import codecs
import contextlib
import glob
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from app.core.contracts import (
    AppError,
    DownloadMode,
    DownloadOptions,
    ErrorKind,
    FinishedCallback,
    IConfig,
    JobState,
    LogCallback,
    Progress,
    ProgressCallback,
)
from app.core.errors import map_stderr
from app.core.filenames import SUBTITLE_EXTS
from app.core.paths import YTDLP_NOT_FOUND_MESSAGE, find_deno, find_ffmpeg, find_ytdlp

try:
    from PySide6.QtCore import QObject, QProcess, QTimer, Signal

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

    def __init__(self, config: IConfig | None = None, parent: QObject | None = None) -> None:
        if _QT_AVAILABLE:
            super().__init__(parent)
        else:
            super().__init__()

        self._on_progress: ProgressCallback | None = None
        self._on_log: LogCallback | None = None
        self._on_finished: FinishedCallback | None = None

        self._config = config
        self._process: QProcess | None = None
        self._stderr_buf: str = ""
        self._line_buffer: LineBuffer = LineBuffer()
        self._stderr_lines: LineBuffer = LineBuffer()
        # Incremental decoders: a multi-byte UTF-8 char split across two reads
        # must not turn into replacement characters (it would corrupt paths).
        self._out_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._err_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._canceled: bool = False
        self._reported: bool = False
        # The running job's options (subtitle-only runs are checked on exit).
        self._options: DownloadOptions | None = None
        # Output paths yt-dlp announces for this job ("Destination:"/"Merging
        # formats into"); used to delete leftover partials on cancel/failure.
        self._dest_files: set[str] = set()
        # Same paths in announcement order (fallback for the final file).
        self._announced: list[str] = []
        # yt-dlp appends each finished file's final path here (--print-to-file).
        self._print_file: str = ""
        self._output_files: list[Path] = []

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

        self._line_buffer = LineBuffer()
        self._stderr_lines = LineBuffer()
        self._out_decoder.reset()
        self._err_decoder.reset()
        self._stderr_buf = ""
        self._canceled = False
        self._reported = False
        self._dest_files = set()
        self._announced = []
        self._output_files = []
        self._options = options

        if not _QT_AVAILABLE:  # pragma: no cover
            return

        ytdlp_path = self._locate_ytdlp()
        if ytdlp_path is None:
            # Never fall back to a bare "yt-dlp" (QProcess would search PATH).
            # Report asynchronously, like a real run, so callers see one flow.
            error = AppError(
                kind=ErrorKind.UNKNOWN,
                user_message=YTDLP_NOT_FOUND_MESSAGE,
            )
            QTimer.singleShot(0, self, lambda: self._report(JobState.FAILED, error))
            return

        fd, self._print_file = tempfile.mkstemp(prefix="ytdlpgui-", suffix=".txt")
        os.close(fd)
        args = build_command(
            options,
            ytdlp_path=ytdlp_path,
            ffmpeg_path=self._locate_ffmpeg(),
            deno_path=self._locate_deno(),
            print_file=self._print_file,
        )

        process = QProcess(self)
        self._process = process

        process.readyReadStandardOutput.connect(self._on_stdout)
        process.readyReadStandardError.connect(self._on_stderr_ready)
        process.finished.connect(self._on_process_finished)
        process.errorOccurred.connect(self._on_process_error)

        program = args[0]
        arguments = args[1:]
        process.start(program, arguments)

    def cancel(self) -> None:
        """Forcibly stop the running process and clean up partial files.

        Uses kill(): yt-dlp is a console app and ignores QProcess.terminate()
        (WM_CLOSE) on Windows, so the download would otherwise keep running.
        Once the process is gone, _on_process_finished deletes the partial
        files (.part/.ytdl/fragments) this job wrote into the output folder.
        """
        if self._process is not None and _QT_AVAILABLE:
            self._canceled = True
            # Kill the whole process tree: yt-dlp may have spawned ffmpeg/a
            # downloader child that QProcess.kill() would leave running (and it
            # could still move a finished file into the output folder).
            pid = self._process.processId()
            if sys.platform == "win32" and pid:
                with contextlib.suppress(Exception):
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        capture_output=True,
                    )
            self._process.kill()
            # _on_process_finished will fire and report CANCELED.

    def shutdown(self) -> None:
        """Cancel and wait for the process, so partials are deleted before the app exits.

        waitForFinished() emits ``finished`` synchronously, which runs the usual
        cleanup and report; without it the runner dies with the window first.
        """
        if self._process is None or not _QT_AVAILABLE:
            return
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return
        self.cancel()
        self._process.waitForFinished(3000)

    # ------------------------------------------------------------------
    # QProcess slots
    # ------------------------------------------------------------------

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        raw = self._out_decoder.decode(bytes(self._process.readAllStandardOutput().data()))
        for line in self._line_buffer.feed(raw):
            self._dispatch_line(line)

    def _on_stderr_ready(self) -> None:
        if self._process is None:
            return
        raw = self._err_decoder.decode(bytes(self._process.readAllStandardError().data()))
        self._stderr_buf += raw
        for line in self._stderr_lines.feed(raw):
            self._dispatch_stderr_line(line)

    def _on_process_error(self, err: object) -> None:
        """Report a process that never started (``finished`` is not emitted then).

        Without this, a wrong/missing yt-dlp path leaves the job RUNNING forever
        and its concurrency slot is never freed. Other errors (e.g. Crashed from
        our own kill()) are followed by ``finished`` and handled there.
        """
        if err != QProcess.ProcessError.FailedToStart:
            return
        error = AppError(
            kind=ErrorKind.UNKNOWN,
            user_message="yt-dlp could not be started. Check its path in Settings → Binaries.",
            raw=self._process.errorString() if self._process is not None else "",
        )
        self._remove_print_file()
        self._report(JobState.CANCELED if self._canceled else JobState.FAILED, error)

    def _on_process_finished(self, exit_code: int, exit_status: object) -> None:
        # Flush any partial line still in the buffers.
        for line in self._line_buffer.feed(self._out_decoder.decode(b"", final=True)):
            self._dispatch_line(line)
        for line in self._line_buffer.flush():
            self._dispatch_line(line)
        tail = self._err_decoder.decode(b"", final=True)
        self._stderr_buf += tail
        for line in self._stderr_lines.feed(tail) + self._stderr_lines.flush():
            self._dispatch_stderr_line(line)

        error: AppError | None = None
        if self._canceled:
            state = JobState.CANCELED
        elif exit_code == 0:
            state = JobState.COMPLETED
        else:
            state = JobState.FAILED
            error = map_stderr(self._stderr_buf)

        # On cancel/failure, delete the partial files this job wrote so the
        # output folder never keeps a half-finished download. On success the
        # final file stays (yt-dlp already removed its own intermediates).
        if state is not JobState.COMPLETED:
            self._cleanup_partials()
        else:
            self._output_files = self._collect_outputs()
            error = self._missing_subtitles_error()
            if error is not None:
                state = JobState.FAILED
        self._remove_print_file()

        self._report(state, error)

    def _missing_subtitles_error(self) -> AppError | None:
        """A subtitle-only run that wrote no subtitle file is a failure, not "done".

        yt-dlp exits 0 when a video simply has no subtitle in the requested
        language (common for music), so without this check the job would show
        "done" with nothing on disk.
        """
        opts = self._options
        if opts is None or opts.mode != DownloadMode.SUBTITLE:
            return None
        if any(p.suffix.lower() in SUBTITLE_EXTS for p in self._output_files):
            return None
        langs = ", ".join(opts.subtitle_langs) or "the chosen language"
        return AppError(
            kind=ErrorKind.UNAVAILABLE,
            user_message=f"No subtitles in {langs} for this video.",
            raw=self._stderr_buf,
        )

    def output_files(self) -> list[Path]:
        """Final file(s) of a COMPLETED run (empty otherwise / if unknown)."""
        return list(self._output_files)

    def _collect_outputs(self) -> list[Path]:
        """Final paths from the --print-to-file list, else the last announced one.

        The print file holds one ``after_move`` filepath per finished media file.
        It stays empty when no media is post-processed (subtitle-only), so fall
        back to the last path yt-dlp announced that exists on disk.
        """
        printed: list[Path] = []
        if self._print_file:
            with contextlib.suppress(OSError):
                text = Path(self._print_file).read_text(encoding="utf-8")
                printed = [Path(ln.strip()) for ln in text.splitlines() if ln.strip()]
        found = [p for p in dict.fromkeys(printed) if p.is_file()]
        if found:
            return found
        subs = [p for p in dict.fromkeys(map(Path, self._announced)) if p.is_file()]
        if subs and all(p.suffix.lower() in SUBTITLE_EXTS for p in subs):
            return subs  # subtitle-only run: every written subtitle file
        return subs[-1:]

    def _remove_print_file(self) -> None:
        if self._print_file:
            with contextlib.suppress(OSError):
                os.remove(self._print_file)
            self._print_file = ""

    def _report(self, state: JobState, error: AppError | None) -> None:
        """Invoke ``on_finished`` exactly once per ``start()``."""
        if self._reported:
            return
        self._reported = True
        if self._on_finished:
            self._on_finished(state, error)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _dispatch_line(self, line: str) -> None:
        line = line.rstrip("\r")
        prog = parse_progress_line(line)
        if prog is not None:
            if self._on_progress:
                self._on_progress(prog)
            return
        self._scan_destination(line)
        if line.strip() and self._on_log:
            self._on_log(line)

    def _dispatch_stderr_line(self, line: str) -> None:
        line = line.rstrip("\r")
        self._scan_destination(line)
        if self._on_log:
            self._on_log(line)

    def _scan_destination(self, line: str) -> None:
        """Record output paths yt-dlp announces so we can delete partials later.

        yt-dlp prints one ``[...] Destination: <path>`` per stream/extracted
        file, and ``Merging formats into "<path>"`` for the merged result. The
        on-disk partial is that path or ``<path>.part`` (plus ``.ytdl`` and
        ``.part-FragN`` fragment files).
        """
        for marker in ("Destination: ", "Writing video subtitles to: "):
            idx = line.find(marker)
            if idx != -1:
                self._record(line[idx + len(marker) :].strip().strip('"'))
                return
        if "Merging formats into " in line:
            first = line.find('"')
            last = line.rfind('"')
            if first != -1 and last > first:
                self._record(line[first + 1 : last])

    def _record(self, path: str) -> None:
        if path:
            self._dest_files.add(path)
            self._announced.append(path)

    def _cleanup_partials(self) -> None:
        """Delete this job's leftover files from the output folder.

        Removes each announced destination plus its ``.part``/``.ytdl`` and
        fragment siblings. Scoped to the paths *this* job reported, so a
        concurrent download into the same folder is never touched.
        """
        for dest in self._dest_files:
            self._remove_path(dest)
            self._remove_path(dest + ".ytdl")
            for sibling in glob.glob(glob.escape(dest) + ".part*"):
                self._remove_path(sibling)
        self._dest_files.clear()

    @staticmethod
    def _remove_path(path: str) -> None:
        """Delete a file, retrying briefly while a killed child still holds it."""
        for _ in range(10):
            if not os.path.exists(path):
                return
            try:
                os.remove(path)
                return
            except OSError:
                time.sleep(0.1)

    def _configured(self, key: str) -> str:
        """Binary path the user set in Settings → Binaries ("" = auto-detect)."""
        if self._config is None:
            return ""
        try:
            return str(self._config.get(key) or "")
        except Exception:
            return ""

    def _locate_ytdlp(self) -> str | None:
        """Configured path, else the app's install folder; None if neither has it."""
        found = find_ytdlp(self._configured("ytdlp_path"))
        return str(found) if found else None

    def _locate_ffmpeg(self) -> str:
        """Same order for ffmpeg; empty string lets yt-dlp use its own lookup."""
        found = find_ffmpeg(self._configured("ffmpeg_path"))
        return str(found) if found else ""

    def _locate_deno(self) -> str:
        """Same order for deno (YouTube's JS challenge); "" if it isn't there."""
        found = find_deno(self._configured("deno_path"))
        return str(found) if found else ""
