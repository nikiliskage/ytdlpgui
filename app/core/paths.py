"""Binary (yt-dlp / ffmpeg) location resolution for ytdlpgui (Stream A).

Resolution order for both binaries:
  1. Explicit path from config (Settings → Binaries; if the file exists)
  2. The application's own folder — next to the .exe when packaged (so users just
     drop yt-dlp.exe / ffmpeg.exe beside the app), or the repo root in dev

Nothing else is searched (no PATH, no well-known folders): the app only ever
runs binaries the user put beside it or chose explicitly.

Version detection uses no_window_kwargs() to suppress console flash on Windows.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from app.core.contracts import BinaryStatus

# Download/info URLs shown to the user when a binary is missing.
_YTDLP_DOWNLOAD_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest"
_FFMPEG_DOWNLOAD_URL = "https://ffmpeg.org/download.html"

# Shown wherever a missing yt-dlp stops the app (splash, fetch, download).
YTDLP_NOT_FOUND_MESSAGE = (
    "yt-dlp not found. Put yt-dlp.exe next to the app, or set it in Settings → Binaries."
)


def app_binary_dir() -> Path:
    """Folder to search for the binaries that live alongside the app.

    When packaged with PyInstaller this is the directory of the running ``.exe``
    (the install folder, where the user keeps yt-dlp.exe / ffmpeg.exe). In a
    source checkout it is the repository root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def documents_dir() -> Path:
    """The user's Documents folder (honours OneDrive redirection on Windows)."""
    if sys.platform == "win32":
        try:
            import ctypes

            buf = ctypes.create_unicode_buffer(260)
            # SHGetFolderPathW(None, CSIDL_PERSONAL=0x0005, None, 0, buf)
            ctypes.windll.shell32.SHGetFolderPathW(None, 0x0005, None, 0, buf)
            if buf.value:
                return Path(buf.value)
        except Exception:
            pass
    return Path.home() / "Documents"


def default_download_base() -> Path:
    """Default base for downloads: ``<Documents>\\yt-dlp-gui`` (video/ + audio/)."""
    return documents_dir() / "yt-dlp-gui"


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


def no_window_kwargs() -> dict[str, Any]:
    """Return subprocess keyword arguments that hide the console on Windows.

    On non-Windows platforms returns an empty dict — callers can always
    unpack this safely: ``subprocess.run([...], **no_window_kwargs())``.
    """
    if sys.platform == "win32":
        # CREATE_NO_WINDOW is Windows-only; use getattr to stay importable on Linux.
        flag: int = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return {"creationflags": flag}
    return {}


# ---------------------------------------------------------------------------
# Version detection
# ---------------------------------------------------------------------------


def ytdlp_version(path: Path) -> str | None:
    """Return the yt-dlp version string, or None on failure."""
    try:
        result = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            **no_window_kwargs(),
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def ffmpeg_version(path: Path) -> str | None:
    """Return a short ffmpeg version string parsed from the first output line.

    ``ffmpeg -version`` outputs something like:
        ffmpeg version 7.1 Copyright (c) 2000-2024 ...
    We return just ``"7.1"`` (the token after "version").
    """
    try:
        result = subprocess.run(
            [str(path), "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            **no_window_kwargs(),
        )
        output = result.stdout or result.stderr
        first_line = output.splitlines()[0] if output else ""
        # Expected pattern: "ffmpeg version <VERSION> ..."
        parts = first_line.split()
        # parts: ["ffmpeg", "version", "7.1", ...]
        if len(parts) >= 3 and parts[0].lower() == "ffmpeg" and parts[1] == "version":
            return parts[2]
        # Fallback: return the whole first line trimmed
        return first_line.strip() or None
    except (OSError, subprocess.TimeoutExpired, IndexError):
        pass
    return None


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


def _check_binary(candidates: list[Path]) -> Path | None:
    """Return the first candidate path that is an existing file, or None."""
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Public resolution functions
# ---------------------------------------------------------------------------


def _candidates(name: str, config_path: str) -> list[Path]:
    """Search candidates for *name* in the documented resolution order."""
    candidates: list[Path] = []

    # (a) Explicit config path
    if config_path:
        candidates.append(Path(config_path))

    # (b) Next to the app (the install folder when packaged)
    app_dir = app_binary_dir()
    candidates.append(app_dir / f"{name}.exe")
    candidates.append(app_dir / name)
    return candidates


def find_ytdlp(config_path: str = "") -> Path | None:
    """Locate yt-dlp without running it (cheap; safe to call on the GUI thread)."""
    return _check_binary(_candidates("yt-dlp", config_path))


def find_ffmpeg(config_path: str = "") -> Path | None:
    """Locate ffmpeg without running it (cheap; safe to call on the GUI thread)."""
    return _check_binary(_candidates("ffmpeg", config_path))


def resolve_ytdlp(config_path: str = "") -> BinaryStatus:
    """Resolve yt-dlp binary using the documented search order.

    Args:
        config_path: explicit path from user config (empty string = not set).

    Returns:
        BinaryStatus with found/path/version/message/download_url populated.
    """
    found_path = find_ytdlp(config_path)
    if found_path is None:
        return BinaryStatus(
            found=False,
            path=None,
            version=None,
            message=YTDLP_NOT_FOUND_MESSAGE,
            download_url=_YTDLP_DOWNLOAD_URL,
        )

    version = ytdlp_version(found_path)
    return BinaryStatus(
        found=True,
        path=found_path,
        version=version,
        message=f"Found at {found_path}" + (f" (v{version})" if version else ""),
        download_url=_YTDLP_DOWNLOAD_URL,
    )


def resolve_ffmpeg(config_path: str = "") -> BinaryStatus:
    """Resolve ffmpeg binary using the documented search order.

    Args:
        config_path: explicit path from user config (empty string = not set).

    Returns:
        BinaryStatus with found/path/version/message/download_url populated.
    """
    found_path = find_ffmpeg(config_path)
    if found_path is None:
        return BinaryStatus(
            found=False,
            path=None,
            version=None,
            message=("ffmpeg not found. Put ffmpeg.exe next to the app, or set it in Settings."),
            download_url=_FFMPEG_DOWNLOAD_URL,
        )

    version = ffmpeg_version(found_path)
    return BinaryStatus(
        found=True,
        path=found_path,
        version=version,
        message=f"Found at {found_path}" + (f" (v{version})" if version else ""),
        download_url=_FFMPEG_DOWNLOAD_URL,
    )


# ---------------------------------------------------------------------------
# Update helper
# ---------------------------------------------------------------------------


def update_ytdlp(path: Path) -> tuple[bool, str]:
    """Run ``yt-dlp -U`` to self-update the binary.

    Returns:
        (success, output_text) — success is True when exit code is 0.
    """
    try:
        result = subprocess.run(
            [str(path), "-U"],
            capture_output=True,
            text=True,
            timeout=120,
            **no_window_kwargs(),
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
