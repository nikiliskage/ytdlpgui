"""Cancel/failure cleanup: leftover partials are deleted, scoped to the job.

Exercises the pure-ish helpers on YtDlpRunner (no QProcess/event loop): the
``Destination:`` scanner that records output paths and the partial sweeper that
removes ``.part``/``.ytdl``/fragment files for *this* job only.
"""

from __future__ import annotations

from pathlib import Path

from app.core.ytdlp_runner import YtDlpRunner


def _touch(path: Path) -> None:
    path.write_text("x", encoding="utf-8")


def test_scan_destination_captures_download_and_merge() -> None:
    runner = YtDlpRunner()
    runner._scan_destination(r"[download] Destination: C:\yt-dlp\videos\Clip.f137.mp4")
    runner._scan_destination(r'[Merger] Merging formats into "C:\yt-dlp\videos\Clip.mp4"')
    runner._scan_destination("[download]  50.0% of ...")  # not a destination line
    assert runner._dest_files == {
        r"C:\yt-dlp\videos\Clip.f137.mp4",
        r"C:\yt-dlp\videos\Clip.mp4",
    }


def test_cleanup_partials_removes_part_ytdl_and_fragments(tmp_path: Path) -> None:
    dest = tmp_path / "Clip.f137.mp4"
    part = tmp_path / "Clip.f137.mp4.part"
    frag = tmp_path / "Clip.f137.mp4.part-Frag0"
    ytdl = tmp_path / "Clip.f137.mp4.ytdl"
    for p in (dest, part, frag, ytdl):
        _touch(p)

    runner = YtDlpRunner()
    runner._dest_files = {str(dest)}
    runner._cleanup_partials()

    for p in (dest, part, frag, ytdl):
        assert not p.exists(), f"{p.name} should have been deleted"


def test_cleanup_partials_leaves_other_jobs_files(tmp_path: Path) -> None:
    """Only paths this job reported are removed; a sibling download survives."""
    mine = tmp_path / "Mine.mp4.part"
    other = tmp_path / "Other.mp4.part"
    _touch(mine)
    _touch(other)

    runner = YtDlpRunner()
    runner._dest_files = {str(tmp_path / "Mine.mp4")}
    runner._cleanup_partials()

    assert not mine.exists()
    assert other.exists()
