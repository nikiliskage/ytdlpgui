"""Playlist flow: a playlist link shows the checklist card; checked videos are
queued one job each into <dir>/<playlist>/NN - title; mixed links offer the
playlist from the media card."""

from __future__ import annotations

from pathlib import Path

from app.core import contracts as c


def _playlist(n: int = 3) -> c.PlaylistInfo:
    return c.PlaylistInfo(
        id="PL1",
        title="My: Mix",  # ':' is invalid in a Windows folder name
        items=[
            c.PlaylistItem(id=f"v{i}", title=f"Video {i}", url=f"https://x/v{i}", index=i)
            for i in range(1, n + 1)
        ],
    )


def _fetch(window, url: str = "https://www.youtube.com/playlist?list=PL1") -> None:  # type: ignore[no-untyped-def]
    window.omni.input.setText(url)
    window.omni.fetch_btn.click()


def test_playlist_link_shows_checklist(window, mock_fetcher) -> None:  # type: ignore[no-untyped-def]
    mock_fetcher.playlist = _playlist()
    _fetch(window)
    assert window.playlist_card.isVisible()
    assert not window.media_card.isVisible()
    assert window.playlist_card.list.count() == 3
    assert window.playlist_card.queue_btn.text() == "Add 3 to queue"


def test_queue_selected_items_into_playlist_folder(  # type: ignore[no-untyped-def]
    window, mock_fetcher, mock_runner_factory, mock_config
) -> None:
    mock_config.set("max_concurrent_downloads", 5)
    mock_fetcher.playlist = _playlist()
    _fetch(window)
    window.playlist_card.set_checked(1, False)  # skip "Video 2"
    window.playlist_card.queue_btn.click()

    started = [r.options for r in mock_runner_factory.created]
    assert [o.url for o in started] == ["https://x/v1", "https://x/v3"]
    assert started[0].output_template == "01 - %(title)s.%(ext)s"
    assert started[1].output_template == "03 - %(title)s.%(ext)s"
    assert started[0].video_dir == Path("video") / "My_ Mix"


def test_select_all_toggles_every_row(window, mock_fetcher) -> None:  # type: ignore[no-untyped-def]
    mock_fetcher.playlist = _playlist()
    _fetch(window)
    card = window.playlist_card
    card.select_all.click()  # uncheck all
    assert card.selected_items() == []
    assert not card.queue_btn.isEnabled()
    card.select_all.click()
    assert len(card.selected_items()) == 3


def test_playlist_audio_mode_applies_to_all_items(  # type: ignore[no-untyped-def]
    window, mock_fetcher, mock_runner_factory
) -> None:
    mock_fetcher.playlist = _playlist(2)
    _fetch(window)
    window.playlist_card.segmented.set_mode(c.DownloadMode.AUDIO)
    window.playlist_card.chips.select("mp3")
    window.playlist_card.queue_btn.click()
    for runner in mock_runner_factory.created:
        assert runner.options.mode == c.DownloadMode.AUDIO
        assert runner.options.audio_format == "mp3"


def test_mixed_link_offers_open_playlist(window, mock_fetcher) -> None:  # type: ignore[no-untyped-def]
    _fetch(window, "https://www.youtube.com/watch?v=abc&list=PL1")
    assert window.media_card.isVisible()
    assert window.media_card.has_playlist_link()

    mock_fetcher.playlist = _playlist()
    window.media_card.playlist_btn.click()
    assert mock_fetcher.expanded == ["https://www.youtube.com/playlist?list=PL1"]
    assert window.playlist_card.isVisible()


def test_plain_video_link_has_no_playlist_band(window) -> None:  # type: ignore[no-untyped-def]
    _fetch(window, "https://www.youtube.com/watch?v=abc")
    assert not window.media_card.has_playlist_link()


def test_empty_playlist_shows_error(window, mock_fetcher) -> None:  # type: ignore[no-untyped-def]
    mock_fetcher.playlist = c.PlaylistInfo(id="PL1", title="Empty")
    _fetch(window)
    assert window.error_band.isVisible()
    assert not window.playlist_card.isVisible()


def test_subtitle_mode_warns_about_missing_subtitles(window, mock_fetcher) -> None:  # type: ignore[no-untyped-def]
    mock_fetcher.playlist = _playlist()
    _fetch(window)
    card = window.playlist_card
    assert card.sub_note.isHidden()
    card.segmented.set_mode(c.DownloadMode.SUBTITLE)
    assert not card.sub_note.isHidden()


def test_retry_after_open_playlist_error_re_expands(window, mock_fetcher) -> None:  # type: ignore[no-untyped-def]
    """Retry on a failed "Open playlist" expands the playlist again, not the video."""
    _fetch(window, "https://www.youtube.com/watch?v=abc&list=PL1")
    mock_fetcher.fail_with = c.AppError(kind=c.ErrorKind.NETWORK, user_message="offline")
    window.media_card.playlist_btn.click()
    assert window.error_band.isVisible()

    mock_fetcher.fail_with = None
    mock_fetcher.playlist = _playlist()
    window.error_band.retry.emit()

    assert mock_fetcher.expanded == ["https://www.youtube.com/playlist?list=PL1"] * 2
    assert window.playlist_card.isVisible()
