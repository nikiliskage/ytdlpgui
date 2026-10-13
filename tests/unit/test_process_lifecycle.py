"""Real-QProcess lifecycle: start failures, configured paths, superseded fetches.

These spawn real processes (the test's own Python, or a path that does not
exist) — no yt-dlp or network needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.core import contracts as c
from app.core.format_fetcher import FormatFetcher
from app.core.ytdlp_runner import YtDlpRunner


class _Cfg:
    def __init__(self, **values: object) -> None:
        self._values = values

    def get(self, key: str) -> object:
        return self._values.get(key, "")

    def set(self, key: str, value: object) -> None:
        self._values[key] = value

    def save(self) -> None:
        pass


# ---------------------------------------------------------------------------
# YtDlpRunner
# ---------------------------------------------------------------------------


def test_runner_uses_configured_binary_paths(tmp_path: Path) -> None:
    ytdlp = tmp_path / "my-yt-dlp.exe"
    ffmpeg = tmp_path / "my-ffmpeg.exe"
    ytdlp.write_text("fake")
    ffmpeg.write_text("fake")

    runner = YtDlpRunner(_Cfg(ytdlp_path=str(ytdlp), ffmpeg_path=str(ffmpeg)))

    assert runner._locate_ytdlp() == str(ytdlp)
    assert runner._locate_ffmpeg() == str(ffmpeg)


def test_runner_reports_failure_when_binary_cannot_start(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """FailedToStart emits no ``finished``; the job must still end (and only once)."""
    runner = YtDlpRunner()
    runner._locate_ytdlp = lambda: str(tmp_path / "missing" / "yt-dlp.exe")  # type: ignore[method-assign]
    runner._locate_ffmpeg = lambda: ""  # type: ignore[method-assign]
    results: list[tuple[c.JobState, c.AppError | None]] = []
    runner.set_callbacks(lambda _p: None, lambda _l: None, lambda s, e: results.append((s, e)))

    runner.start(c.DownloadOptions(url="https://x/v", video_dir=tmp_path))

    qtbot.waitUntil(lambda: bool(results), timeout=5000)
    qtbot.wait(100)
    assert len(results) == 1
    state, error = results[0]
    assert state == c.JobState.FAILED
    assert error is not None and "could not be started" in error.user_message


# ---------------------------------------------------------------------------
# FormatFetcher
# ---------------------------------------------------------------------------


def test_fetcher_reads_configured_path_on_every_fetch(tmp_path: Path) -> None:
    first = tmp_path / "a.exe"
    second = tmp_path / "b.exe"
    first.write_text("fake")
    second.write_text("fake")
    cfg = _Cfg(ytdlp_path=str(first))
    fetcher = FormatFetcher(cfg)
    assert fetcher._locate_ytdlp() == str(first)

    cfg.set("ytdlp_path", str(second))  # changed in Settings, no restart
    assert fetcher._locate_ytdlp() == str(second)


def test_superseded_fetch_result_is_dropped(qtbot) -> None:  # type: ignore[no-untyped-def]
    """A slow earlier fetch must not be delivered in place of the newer one."""
    fetcher = FormatFetcher()
    fetcher._locate_ytdlp = lambda: sys.executable  # type: ignore[method-assign]
    delivered: list[str] = []

    fetcher._run(
        ["-c", "import time; time.sleep(1.5); print('old')"],
        lambda o, _e: delivered.append(o.strip()),
    )
    fetcher._run(["-c", "print('new')"], lambda o, _e: delivered.append(o.strip()))

    qtbot.waitUntil(lambda: bool(delivered), timeout=10000)
    qtbot.wait(2000)  # give the old process time to (not) report
    assert delivered == ["new"]


def test_canceled_fetch_never_reports(qtbot) -> None:  # type: ignore[no-untyped-def]
    fetcher = FormatFetcher()
    fetcher._locate_ytdlp = lambda: sys.executable  # type: ignore[method-assign]
    delivered: list[str] = []

    fetcher._run(["-c", "print('x')"], lambda o, _e: delivered.append(o))
    fetcher.cancel()

    qtbot.wait(1500)
    assert delivered == []


def test_handle_flat_null_reports_error_without_crashing() -> None:
    fetcher = FormatFetcher()
    done: list[list[c.PlaylistItem]] = []
    errors: list[c.AppError] = []
    fetcher._handle_flat("null", "ERROR: Video unavailable", done.append, errors.append)
    assert not done
    assert len(errors) == 1
