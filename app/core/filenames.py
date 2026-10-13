"""Windows-safe file names and renaming of finished downloads (pure, no Qt).

Shared by the queue's "Rename" action and the playlist subfolder naming.
"""

from __future__ import annotations

import contextlib
import re
from pathlib import Path

# Characters Windows forbids in a file name, plus ASCII control characters.
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Device names Windows reserves regardless of extension (CON.mp4 is invalid too).
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

SUBTITLE_EXTS = {".vtt", ".srt", ".ass", ".ssa", ".ttml", ".srv1", ".srv2", ".srv3", ".json3"}

# Files yt-dlp writes next to the media (subtitles, thumbnail, metadata) that
# should follow it on rename. Anything else sharing the stem is left alone.
_SIDECAR_EXTS = {
    *SUBTITLE_EXTS,
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".json",
    ".description",
}

# Keep names well below MAX_PATH so the folder + extension still fit.
_MAX_STEM = 150


def sanitize_filename(name: str, fallback: str = "untitled") -> str:
    """Turn *name* into a valid Windows file/folder name (no extension handling).

    Forbidden characters become ``_``, runs of whitespace collapse, trailing dots
    and spaces are stripped (Windows drops them silently), reserved device names
    get a ``_`` suffix, and an empty result becomes *fallback*.
    """
    cleaned = _INVALID.sub("_", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned[:_MAX_STEM].rstrip(" .")
    if not cleaned:
        return fallback
    if cleaned.split(".")[0].upper() in _RESERVED:
        cleaned += "_"
    return cleaned


def playlist_item_template(index: int, total: int) -> str:
    """yt-dlp output template that keeps playlist order: ``07 - %(title)s.%(ext)s``.

    Each playlist item is downloaded as its own single-video job, so yt-dlp's
    ``%(playlist_index)s`` is unavailable; the index is baked in instead, padded
    to the width of *total* (at least 2 digits) so names sort correctly.
    """
    width = max(2, len(str(max(total, index))))
    return f"{index:0{width}d} - %(title)s.%(ext)s"


def rename_output(path: Path, new_stem: str) -> Path:
    """Rename a downloaded file to *new_stem*, keeping its extension.

    Sidecar files that share the old stem (``Clip.en.vtt``, ``Clip.webp``…) are
    renamed along with it so subtitles/thumbnails stay paired with the media.

    Returns the new path. Raises ``FileExistsError`` if any target already
    exists (nothing is renamed then), ``FileNotFoundError`` if *path* is gone,
    and ``ValueError`` if *new_stem* is empty after sanitizing.
    """
    stem = sanitize_filename(new_stem, fallback="")
    if not stem:
        raise ValueError("The new name is empty.")
    if not path.is_file():
        raise FileNotFoundError(path)
    if stem == path.stem:
        return path

    old_stem = path.stem
    sidecars = [
        p
        for p in path.parent.iterdir()
        if p != path
        and p.is_file()
        and p.name.startswith(old_stem + ".")
        and p.suffix.lower() in _SIDECAR_EXTS
    ]
    moves = [(path, path.with_name(stem + path.suffix))]
    moves += [(p, p.with_name(stem + p.name[len(old_stem) :])) for p in sidecars]

    # Check every target first so a clash never leaves a half-renamed set.
    for _src, dst in moves:
        if dst.exists() and dst.resolve() != _src.resolve():
            raise FileExistsError(dst)
    done: list[tuple[Path, Path]] = []
    try:
        for src, dst in moves:
            src.rename(dst)
            done.append((src, dst))
    except OSError:
        # e.g. a sidecar is locked by a player: undo so the set stays paired.
        for src, dst in reversed(done):
            with contextlib.suppress(OSError):
                dst.rename(src)
        raise
    return moves[0][1]
