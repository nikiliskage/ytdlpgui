"""Real yt-dlp download through YtDlpRunner (network; skipped by default).

Run with:  pytest -m network tests/unit/test_real_download.py
Binaries come from $YTDLPGUI_TEST_BIN (a folder with yt-dlp.exe, ffmpeg.exe and
deno.exe) or C:\\yt-dlp. deno can also be given on its own via $YTDLPGUI_TEST_DENO.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from app.core import contracts as c
from app.core.filenames import rename_output
from app.core.ytdlp_runner import YtDlpRunner

pytestmark = pytest.mark.network

_BIN = Path(os.environ.get("YTDLPGUI_TEST_BIN", r"C:\yt-dlp"))
_DENO = os.environ.get("YTDLPGUI_TEST_DENO", str(_BIN / "deno.exe"))
_URL = "https://www.youtube.com/watch?v=t-E2gm0a_N0"


class _Cfg:
    def get(self, key: str) -> object:
        return {
            "ytdlp_path": str(_BIN / "yt-dlp.exe"),
            "ffmpeg_path": str(_BIN / "ffmpeg.exe"),
            "deno_path": _DENO,
        }.get(key, "")

    def set(self, key: str, value: object) -> None:
        pass

    def save(self) -> None:
        pass


@pytest.fixture
def runner() -> YtDlpRunner:
    if not (_BIN / "yt-dlp.exe").is_file() or not Path(_DENO).is_file():
        pytest.skip("needs yt-dlp.exe + deno.exe (see module docstring)")
    return YtDlpRunner(_Cfg())


def _run(qtbot, runner: YtDlpRunner, opts: c.DownloadOptions):  # type: ignore[no-untyped-def]
    results: list[tuple[c.JobState, c.AppError | None]] = []
    runner.set_callbacks(lambda _p: None, lambda _l: None, lambda s, e: results.append((s, e)))
    runner.start(opts)
    qtbot.waitUntil(lambda: bool(results), timeout=240_000)
    return results[0]


def test_audio_download_reports_its_file_and_can_be_renamed(qtbot, runner, tmp_path) -> None:  # type: ignore[no-untyped-def]
    opts = c.DownloadOptions(
        url=_URL, mode=c.DownloadMode.AUDIO, audio_dir=tmp_path, audio_format="best"
    )
    state, error = _run(qtbot, runner, opts)
    assert state == c.JobState.COMPLETED, error
    [path] = runner.output_files()
    assert path.is_file() and path.parent == tmp_path
    renamed = rename_output(path, "Renamed track")
    assert renamed.is_file() and renamed.stem == "Renamed track"


def test_subtitle_only_without_subtitles_fails(qtbot, runner, tmp_path) -> None:  # type: ignore[no-untyped-def]
    opts = c.DownloadOptions(
        url=_URL, mode=c.DownloadMode.SUBTITLE, video_dir=tmp_path, subtitle_langs=["en"]
    )
    state, error = _run(qtbot, runner, opts)
    assert state == c.JobState.FAILED
    assert error is not None and "No subtitles" in error.user_message
