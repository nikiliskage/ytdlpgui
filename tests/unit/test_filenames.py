"""Windows-safe names and post-download renaming (app.core.filenames)."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.filenames import playlist_item_template, rename_output, sanitize_filename

# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('a<b>c:d"e/f\\g|h?i*j', "a_b_c_d_e_f_g_h_i_j"),
        ("  spaced   out  ", "spaced out"),
        ("trailing dots...", "trailing dots"),
        ("Şarkı — Türkçe", "Şarkı — Türkçe"),
        ("CON", "CON_"),
        ("nul.txt", "nul.txt_"),
        ("", "untitled"),
        ("...", "untitled"),
    ],
)
def test_sanitize_filename(raw: str, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_caps_length() -> None:
    assert len(sanitize_filename("x" * 500)) <= 150


# ---------------------------------------------------------------------------
# playlist_item_template
# ---------------------------------------------------------------------------


def test_playlist_item_template_pads_to_total_width() -> None:
    assert playlist_item_template(3, 9) == "03 - %(title)s.%(ext)s"
    assert playlist_item_template(7, 120) == "007 - %(title)s.%(ext)s"


# ---------------------------------------------------------------------------
# rename_output
# ---------------------------------------------------------------------------


def _touch(path: Path) -> Path:
    path.write_text("x", encoding="utf-8")
    return path


def test_rename_keeps_extension_and_moves_sidecars(tmp_path: Path) -> None:
    media = _touch(tmp_path / "Clip.mp4")
    sub = _touch(tmp_path / "Clip.en.vtt")
    thumb = _touch(tmp_path / "Clip.webp")
    unrelated = _touch(tmp_path / "Clip.part2.mp4")  # not a sidecar — left alone

    new = rename_output(media, "My clip")

    assert new == tmp_path / "My clip.mp4"
    assert new.is_file() and not media.exists()
    assert (tmp_path / "My clip.en.vtt").is_file() and not sub.exists()
    assert (tmp_path / "My clip.webp").is_file() and not thumb.exists()
    assert unrelated.is_file()


def test_rename_sanitizes_the_new_name(tmp_path: Path) -> None:
    media = _touch(tmp_path / "Clip.mp4")
    assert rename_output(media, "a/b: c?") == tmp_path / "a_b_ c_.mp4"


def test_rename_clash_raises_and_renames_nothing(tmp_path: Path) -> None:
    media = _touch(tmp_path / "Clip.mp4")
    sub = _touch(tmp_path / "Clip.en.vtt")
    _touch(tmp_path / "Taken.en.vtt")  # the sidecar's target already exists

    with pytest.raises(FileExistsError):
        rename_output(media, "Taken")

    assert media.is_file() and sub.is_file()


def test_rename_same_name_is_a_no_op(tmp_path: Path) -> None:
    media = _touch(tmp_path / "Clip.mp4")
    assert rename_output(media, "Clip") == media


def test_rename_missing_file_or_empty_name(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        rename_output(tmp_path / "gone.mp4", "x")
    media = _touch(tmp_path / "Clip.mp4")
    with pytest.raises(ValueError):
        rename_output(media, "  ...  ")


def test_rename_failure_midway_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A locked sidecar must not leave the media and its subtitle with different names."""
    media = _touch(tmp_path / "Clip.mp4")
    sub = _touch(tmp_path / "Clip.en.vtt")
    real_rename = Path.rename

    def flaky(self: Path, target: Path) -> Path:
        if self.suffix == ".vtt":
            raise PermissionError("locked")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", flaky)
    with pytest.raises(PermissionError):
        rename_output(media, "New")

    assert media.is_file() and sub.is_file()
    assert not (tmp_path / "New.mp4").exists()
