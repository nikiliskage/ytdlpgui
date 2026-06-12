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
    card.chips.select("720p")
    assert state.quality == "720p"
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
    card.chips.select("1080p")
    assert state.quality == "1080p"
    assert state.selected_format is None


def test_subtitle_mode_hides_advanced(qtbot) -> None:  # type: ignore[no-untyped-def]
    _state, card = _card(qtbot)
    card.segmented.set_mode(c.DownloadMode.SUBTITLE)
    assert card.formats.isHidden()
    card.segmented.set_mode(c.DownloadMode.VIDEO)
    assert not card.formats.isHidden()


def test_subtitle_chips_grey_unavailable_and_preselect(qtbot, mock_config) -> None:  # type: ignore[no-untyped-def]
    mock_config.set("subtitle_langs", ["en", "tr", "de"])
    state = UiState()
    card = MediaCard(state, reduced_motion=True, config=mock_config)
    qtbot.addWidget(card)
    # Video has a manual subtitle only for tr; en and de are unavailable.
    card.set_media(c.MediaInfo(title="X", subtitle_langs=["tr"]), [])
    card.segmented.set_mode(c.DownloadMode.SUBTITLE)
    chips = card.sub_chips
    assert not chips._chips["en"].isEnabled()  # no manual sub → disabled  # noqa: SLF001
    assert chips._chips["tr"].isEnabled()  # noqa: SLF001
    assert not chips._chips["de"].isEnabled()  # no manual sub → disabled  # noqa: SLF001
    assert state.selected_subs == ["tr"]  # first available preselected (single)
    assert card._sub_note.isVisibleTo(card)  # en/de greyed → note shown  # noqa: SLF001


def test_subtitle_region_variant_is_available(qtbot, mock_config) -> None:  # type: ignore[no-untyped-def]
    mock_config.set("subtitle_langs", ["en", "de"])
    state = UiState()
    card = MediaCard(state, reduced_motion=True, config=mock_config)
    qtbot.addWidget(card)
    # Video lists German as "de-DE"; configured "de" should still match.
    card.set_media(c.MediaInfo(title="X", subtitle_langs=["en", "de-DE"]), [])
    card.segmented.set_mode(c.DownloadMode.SUBTITLE)
    assert card.sub_chips._chips["en"].isEnabled()  # noqa: SLF001
    assert card.sub_chips._chips["de"].isEnabled()  # de ↔ de-DE  # noqa: SLF001


def test_refresh_subtitles_after_config_change(qtbot, mock_config) -> None:  # type: ignore[no-untyped-def]
    mock_config.set("subtitle_langs", ["en"])
    state = UiState()
    card = MediaCard(state, reduced_motion=True, config=mock_config)
    qtbot.addWidget(card)
    card.set_media(c.MediaInfo(title="X", subtitle_langs=["en", "de"]), [])
    card.segmented.set_mode(c.DownloadMode.SUBTITLE)
    assert set(card.sub_chips._chips) == {"en"}  # noqa: SLF001
    # Settings change adds German; refresh picks it up without a mode switch.
    mock_config.set("subtitle_langs", ["en", "de"])
    card.refresh_subtitles()
    assert set(card.sub_chips._chips) == {"en", "de"}  # noqa: SLF001


def test_subtitle_chips_single_select(qtbot, mock_config) -> None:  # type: ignore[no-untyped-def]
    mock_config.set("subtitle_langs", ["en", "tr", "de"])
    state = UiState()
    card = MediaCard(state, reduced_motion=True, config=mock_config)
    qtbot.addWidget(card)
    card.set_media(c.MediaInfo(title="X", subtitle_langs=["en", "tr", "de"]), [])
    card.segmented.set_mode(c.DownloadMode.SUBTITLE)
    assert state.selected_subs == ["en"]  # first available preselected
    card.sub_chips._chips["de"].click()  # switches selection  # noqa: SLF001
    assert state.selected_subs == ["de"]  # single-select: only one active
    card.sub_chips._chips["de"].click()  # active click → no deselect  # noqa: SLF001
    assert state.selected_subs == ["de"]  # one always stays selected
    card.sub_chips._chips["en"].click()  # switch to another available  # noqa: SLF001
    assert state.selected_subs == ["en"]


def test_dest_label_reflects_configured_folder(qtbot, mock_config) -> None:  # type: ignore[no-untyped-def]
    mock_config.set("video_subfolder", "videosad")
    mock_config.set("audio_subfolder", "tunes")
    state = UiState()
    card = MediaCard(state, reduced_motion=True, config=mock_config)
    qtbot.addWidget(card)
    card.refresh_dest()
    assert card._dest_label.text() == "videosad\\"  # noqa: SLF001
    card.segmented.set_mode(c.DownloadMode.AUDIO)
    assert card._dest_label.text() == "tunes\\"  # noqa: SLF001
