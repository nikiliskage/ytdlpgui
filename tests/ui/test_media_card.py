"""Mode switch resets quality + clears table selection + hides Advanced."""

from __future__ import annotations

from app.core import contracts as c
from app.ui_state import UiState
from app.widgets.media_card import MediaCard


def _card(qtbot):  # type: ignore[no-untyped-def]
    state = UiState()
    card = MediaCard(state, reduced_motion=True)
    qtbot.addWidget(card)
    card.set_media(
        c.MediaInfo(title="Sample", channel="Chan", duration=100),
        [c.FormatInfo(format_id="137", ext="mp4", resolution="1920x1080", fps=30)],
    )
    return state, card


def test_mode_switch_resets_quality(qtbot) -> None:  # type: ignore[no-untyped-def]
    state, card = _card(qtbot)
    card.chips.select("720")
    assert state.quality == "720"
    card.segmented.set_mode(c.DownloadMode.AUDIO)
    assert state.mode == c.DownloadMode.AUDIO
    assert state.quality == "bestaudio"  # first audio chip


def test_format_selection_clears_chips_and_vice_versa(qtbot) -> None:  # type: ignore[no-untyped-def]
    state, card = _card(qtbot)
    card.formats.set_open(True)
    card.formats.table.selectRow(0)
    assert state.selected_format == "137"
    assert state.quality is None
    assert card.chips.selected() is None
    # picking a chip again clears the format
    card.chips.select("1080")
    assert state.quality == "1080"
    assert state.selected_format is None


def test_subtitle_mode_hides_advanced(qtbot) -> None:  # type: ignore[no-untyped-def]
    _state, card = _card(qtbot)
    card.segmented.set_mode(c.DownloadMode.SUBTITLE)
    assert card.formats.isHidden()
    card.segmented.set_mode(c.DownloadMode.VIDEO)
    assert not card.formats.isHidden()
