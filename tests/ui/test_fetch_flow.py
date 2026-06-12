"""Fetch flow: clicking Fetch calls the injected fetcher; success → media card,
error → error band."""

from __future__ import annotations

from app.core import contracts as c


def test_fetch_calls_injected_fetcher(window, mock_fetcher) -> None:  # type: ignore[no-untyped-def]
    calls: list[str] = []
    original = mock_fetcher.fetch_formats

    def spy(url, on_done, on_error):  # type: ignore[no-untyped-def]
        calls.append(url)
        original(url, on_done, on_error)

    mock_fetcher.fetch_formats = spy  # type: ignore[method-assign]
    window.omni.input.setText("https://youtube.com/watch?v=abc")
    window.omni.fetch_btn.click()
    assert calls == ["https://youtube.com/watch?v=abc"]


def test_success_shows_media_card(window) -> None:  # type: ignore[no-untyped-def]
    window.omni.input.setText("https://youtube.com/watch?v=abc")
    window.omni.fetch_btn.click()
    assert window.media_card.isVisible()
    assert not window.error_band.isVisible()
    assert window.state.phase == c.AppPhase.LOADED


def test_error_shows_error_band(window, mock_fetcher) -> None:  # type: ignore[no-untyped-def]
    mock_fetcher.fail_with = c.AppError(user_message="HTTP 403")
    window.omni.input.setText("https://youtube.com/watch?v=abc")
    window.omni.fetch_btn.click()
    assert window.error_band.isVisible()
    assert not window.media_card.isVisible()
    assert window.state.phase == c.AppPhase.EMPTY


def test_omni_docks_after_fetch(window) -> None:  # type: ignore[no-untyped-def]
    window.omni.input.setText("https://youtube.com/watch?v=abc")
    window.omni.fetch_btn.click()
    assert not window.omni._hero.isVisible()  # noqa: SLF001


def test_build_options_subtitle_uses_chip_selection(window) -> None:  # type: ignore[no-untyped-def]
    window.state.url = "https://youtube.com/watch?v=abc"
    window.state.mode = c.DownloadMode.SUBTITLE
    window.state.media = c.MediaInfo(
        title="X", subtitle_langs=["en"], auto_caption_langs=["de"]
    )
    window.state.selected_subs = ["en", "de"]
    opts = window._build_options()  # noqa: SLF001
    assert opts.subtitle_langs == ["en", "de"]
    assert opts.write_auto_subs is True  # 'de' is auto-only → enable auto subs
