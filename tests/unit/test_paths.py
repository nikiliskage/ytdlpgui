"""Tests for app.core.paths — binary resolution, version parsing, helpers (Stream A)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import app.core.paths as paths_module
import pytest
from app.core.paths import (
    ffmpeg_version,
    find_ffmpeg,
    find_ytdlp,
    no_window_kwargs,
    resolve_ffmpeg,
    resolve_ytdlp,
    update_ytdlp,
    ytdlp_version,
)

# ---------------------------------------------------------------------------
# no_window_kwargs
# ---------------------------------------------------------------------------


def test_no_window_kwargs_on_windows() -> None:
    """On Windows, no_window_kwargs returns creationflags=CREATE_NO_WINDOW."""
    original = paths_module.sys.platform
    paths_module.sys.platform = "win32"
    try:
        kwargs = no_window_kwargs()
        assert "creationflags" in kwargs
        # CREATE_NO_WINDOW is Windows-only; fall back to its numeric value on Linux.
        expected_flag: int = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        assert kwargs["creationflags"] == expected_flag
    finally:
        paths_module.sys.platform = original


def test_no_window_kwargs_non_windows() -> None:
    """On non-Windows, no_window_kwargs returns an empty dict."""
    original = paths_module.sys.platform
    paths_module.sys.platform = "linux"
    try:
        kwargs = no_window_kwargs()
        assert kwargs == {}
    finally:
        paths_module.sys.platform = original


# ---------------------------------------------------------------------------
# ytdlp_version
# ---------------------------------------------------------------------------


def test_ytdlp_version_parses_output(tmp_path: Path) -> None:
    """ytdlp_version returns the trimmed stdout on success."""
    fake_binary = tmp_path / "yt-dlp.exe"
    fake_binary.write_text("fake")

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "2026.01.15\n"

    with patch("app.core.paths.subprocess.run", return_value=mock_result):
        version = ytdlp_version(fake_binary)

    assert version == "2026.01.15"


def test_ytdlp_version_returns_none_on_error(tmp_path: Path) -> None:
    """ytdlp_version returns None when subprocess raises OSError."""
    fake_binary = tmp_path / "yt-dlp.exe"
    fake_binary.write_text("fake")

    with patch("app.core.paths.subprocess.run", side_effect=OSError("not found")):
        version = ytdlp_version(fake_binary)

    assert version is None


def test_ytdlp_version_returns_none_on_nonzero(tmp_path: Path) -> None:
    """ytdlp_version returns None when exit code != 0."""
    fake_binary = tmp_path / "yt-dlp.exe"
    fake_binary.write_text("fake")

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with patch("app.core.paths.subprocess.run", return_value=mock_result):
        version = ytdlp_version(fake_binary)

    assert version is None


# ---------------------------------------------------------------------------
# ffmpeg_version
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "first_line, expected",
    [
        (
            "ffmpeg version 7.1 Copyright (c) 2000-2024 the FFmpeg developers",
            "7.1",
        ),
        (
            "ffmpeg version 6.0.1-essentials_build-www.gyan.dev",
            "6.0.1-essentials_build-www.gyan.dev",
        ),
        (
            "ffmpeg version N-112053-g62b2e41-20240101",
            "N-112053-g62b2e41-20240101",
        ),
    ],
)
def test_ffmpeg_version_parses_first_line(tmp_path: Path, first_line: str, expected: str) -> None:
    """ffmpeg_version extracts the version token from the first output line."""
    fake_binary = tmp_path / "ffmpeg.exe"
    fake_binary.write_text("fake")

    full_output = first_line + "\nbuilt with gcc 13.2.0\n"
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = full_output
    mock_result.stderr = ""

    with patch("app.core.paths.subprocess.run", return_value=mock_result):
        version = ffmpeg_version(fake_binary)

    assert version == expected


def test_ffmpeg_version_returns_none_on_oserror(tmp_path: Path) -> None:
    """ffmpeg_version returns None when subprocess raises OSError."""
    fake_binary = tmp_path / "ffmpeg.exe"
    fake_binary.write_text("fake")

    with patch("app.core.paths.subprocess.run", side_effect=OSError("not found")):
        version = ffmpeg_version(fake_binary)

    assert version is None


# ---------------------------------------------------------------------------
# resolve_ytdlp / resolve_ffmpeg — config path, then the app folder only
# ---------------------------------------------------------------------------


def _ok_version() -> MagicMock:
    result = MagicMock()
    result.returncode = 0
    result.stdout = "2026.01.01"
    return result


def test_resolve_ytdlp_uses_config_path_first(tmp_path: Path) -> None:
    """A configured path wins over a binary beside the app."""
    explicit_path = tmp_path / "my_ytdlp" / "yt-dlp.exe"
    explicit_path.parent.mkdir(parents=True)
    explicit_path.write_text("fake")
    (tmp_path / "yt-dlp.exe").write_text("fake")

    with (
        patch("app.core.paths.subprocess.run", return_value=_ok_version()),
        patch("app.core.paths.app_binary_dir", return_value=tmp_path),
    ):
        status = resolve_ytdlp(config_path=str(explicit_path))

    assert status.found is True
    assert status.path == explicit_path
    assert status.version == "2026.01.01"


def test_resolve_ytdlp_finds_binary_beside_app(tmp_path: Path) -> None:
    """With no configured path, the install folder (app_binary_dir) is used."""
    beside = tmp_path / "yt-dlp.exe"
    beside.write_text("fake")

    with (
        patch("app.core.paths.subprocess.run", return_value=_ok_version()),
        patch("app.core.paths.app_binary_dir", return_value=tmp_path),
    ):
        status = resolve_ytdlp(config_path="")

    assert status.found is True
    assert status.path == beside


def test_resolve_ytdlp_not_found(tmp_path: Path) -> None:
    """resolve_ytdlp returns found=False with a helpful message when binary is absent."""
    with patch("app.core.paths.app_binary_dir", return_value=tmp_path):
        status = resolve_ytdlp(config_path="")

    assert status.found is False
    assert status.path is None
    assert status.message  # non-empty helpful message
    assert status.download_url  # download URL provided


def test_resolve_ffmpeg_uses_config_path_first(tmp_path: Path) -> None:
    explicit_path = tmp_path / "custom_ffmpeg" / "ffmpeg.exe"
    explicit_path.parent.mkdir(parents=True)
    explicit_path.write_text("fake")

    result = MagicMock()
    result.stdout = "ffmpeg version 7.1 Copyright"
    result.stderr = ""
    with (
        patch("app.core.paths.subprocess.run", return_value=result),
        patch("app.core.paths.app_binary_dir", return_value=tmp_path / "nonexistent"),
    ):
        status = resolve_ffmpeg(config_path=str(explicit_path))

    assert status.found is True
    assert status.path == explicit_path
    assert status.version == "7.1"


def test_resolve_ffmpeg_not_found(tmp_path: Path) -> None:
    with patch("app.core.paths.app_binary_dir", return_value=tmp_path):
        status = resolve_ffmpeg(config_path="")

    assert status.found is False
    assert status.path is None


# ---------------------------------------------------------------------------
# find_ytdlp / find_ffmpeg — locate without running the binary
# ---------------------------------------------------------------------------


def test_find_ytdlp_prefers_config_path_and_never_runs_it(tmp_path: Path) -> None:
    """The configured path wins, and no subprocess (--version) is spawned."""
    explicit = tmp_path / "custom" / "yt-dlp.exe"
    explicit.parent.mkdir()
    explicit.write_text("fake")
    (tmp_path / "yt-dlp.exe").write_text("fake")

    with (
        patch("app.core.paths.app_binary_dir", return_value=tmp_path),
        patch("app.core.paths.subprocess.run") as run,
    ):
        assert find_ytdlp(str(explicit)) == explicit
    run.assert_not_called()


def test_find_ytdlp_missing_config_path_falls_back_to_app_dir(tmp_path: Path) -> None:
    """A stale configured path is skipped in favour of the binary beside the app."""
    beside = tmp_path / "yt-dlp.exe"
    beside.write_text("fake")
    with patch("app.core.paths.app_binary_dir", return_value=tmp_path):
        assert find_ytdlp(str(tmp_path / "gone.exe")) == beside


def test_find_ignores_path_and_legacy_folder(tmp_path: Path) -> None:
    """Binaries on PATH (or in C:\\yt-dlp) are never picked up."""
    on_path = tmp_path / "elsewhere" / "yt-dlp.exe"
    on_path.parent.mkdir()
    on_path.write_text("fake")
    with (
        patch("shutil.which", return_value=str(on_path)),
        patch("app.core.paths.app_binary_dir", return_value=tmp_path / "install"),
    ):
        assert find_ytdlp("") is None
        assert find_ffmpeg("") is None


# ---------------------------------------------------------------------------
# update_ytdlp
# ---------------------------------------------------------------------------


def test_update_ytdlp_success(tmp_path: Path) -> None:
    """update_ytdlp returns (True, output) on success."""
    fake_binary = tmp_path / "yt-dlp.exe"
    fake_binary.write_text("fake")

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "yt-dlp is up to date (2026.01.15)\n"
    mock_result.stderr = ""

    with patch("app.core.paths.subprocess.run", return_value=mock_result):
        ok, output = update_ytdlp(fake_binary)

    assert ok is True
    assert "up to date" in output


def test_update_ytdlp_failure(tmp_path: Path) -> None:
    """update_ytdlp returns (False, message) on OSError."""
    fake_binary = tmp_path / "yt-dlp.exe"
    fake_binary.write_text("fake")

    with patch("app.core.paths.subprocess.run", side_effect=OSError("permission denied")):
        ok, output = update_ytdlp(fake_binary)

    assert ok is False
    assert output  # non-empty error message
