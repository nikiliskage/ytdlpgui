"""Settings change writes to the injected config; cookie toggle reveals note."""

from __future__ import annotations

from app.widgets.settings_panel import SettingsPanel


def test_setting_change_writes_to_config(qtbot, mock_config) -> None:  # type: ignore[no-untyped-def]
    panel = SettingsPanel(mock_config, reduced_motion=True)
    qtbot.addWidget(panel)
    panel.embed_thumb.set_checked(True)
    assert mock_config.get("embed_thumbnail") is True
    assert mock_config.saved > 0


def test_update_message_up_to_date() -> None:
    msg, ok = SettingsPanel._update_message(  # noqa: SLF001
        0, "Latest version: 2026.06.09\nyt-dlp is up to date (2026.06.09)"
    )
    assert ok is True
    assert "up to date" in msg.lower()


def test_update_message_updated() -> None:
    msg, ok = SettingsPanel._update_message(  # noqa: SLF001
        0, "Updating to stable@2026.06.10\nUpdated yt-dlp to 2026.06.10"
    )
    assert ok is True
    assert "2026.06.10" in msg


def test_update_message_failure() -> None:
    msg, ok = SettingsPanel._update_message(  # noqa: SLF001
        1, "ERROR: You installed yt-dlp with pip or using the wheel"
    )
    assert ok is False
    assert msg


def test_slider_writes_max_concurrent(qtbot, mock_config) -> None:  # type: ignore[no-untyped-def]
    panel = SettingsPanel(mock_config, reduced_motion=True)
    qtbot.addWidget(panel)
    panel.max_downloads.setValue(4)
    assert mock_config.get("max_concurrent_downloads") == 4


def test_output_dirs_write_to_config(qtbot, mock_config) -> None:  # type: ignore[no-untyped-def]
    """The Video/Audio folder fields are full-path pickers that persist on edit."""
    panel = SettingsPanel(mock_config, reduced_motion=True)
    qtbot.addWidget(panel)
    panel.video_dir.input.setText(r"D:\clips")
    assert mock_config.get("video_dir") == r"D:\clips"
    panel.audio_dir.input.setText(r"D:\tunes")
    assert mock_config.get("audio_dir") == r"D:\tunes"


def test_subtitle_languages_capped_at_two(qtbot, mock_config) -> None:  # type: ignore[no-untyped-def]
    panel = SettingsPanel(mock_config, reduced_motion=True)
    qtbot.addWidget(panel)
    assert set(panel.sub_langs.selected()) == {"en", "tr"}  # defaults (2)
    panel.sub_langs._pills["de"].click()  # at cap → ignored  # noqa: SLF001
    assert mock_config.get("subtitle_langs") == ["en", "tr"]
    panel.sub_langs._pills["en"].click()  # free a slot  # noqa: SLF001
    panel.sub_langs._pills["de"].click()  # now de fits  # noqa: SLF001
    assert mock_config.get("subtitle_langs") == ["tr", "de"]  # option order preserved
    assert mock_config.saved > 0


def test_cookie_toggle_reveals_note(qtbot, mock_config) -> None:  # type: ignore[no-untyped-def]
    mock_config.set("cookies_consent_accepted", True)  # skip the one-time disclaimer
    panel = SettingsPanel(mock_config, reduced_motion=True)
    qtbot.addWidget(panel)
    panel.show()
    assert not panel._note.isVisible()  # noqa: SLF001
    panel.cookies_toggle.set_checked(True)
    assert panel._note.isVisible()  # noqa: SLF001
    assert mock_config.get("cookies_enabled") is True


def test_cookie_consent_declined_reverts(qtbot, mock_config, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    panel = SettingsPanel(mock_config, reduced_motion=True)
    qtbot.addWidget(panel)
    monkeypatch.setattr(panel, "_ask_cookie_consent", lambda: False)
    panel.cookies_toggle.set_checked(True)
    assert mock_config.get("cookies_enabled") is False  # reverted
    assert not panel.cookies_toggle.is_checked()
    assert not panel._note.isVisible()  # noqa: SLF001


def test_cookie_consent_accepted_enables_and_remembers(qtbot, mock_config, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    panel = SettingsPanel(mock_config, reduced_motion=True)
    qtbot.addWidget(panel)
    monkeypatch.setattr(panel, "_ask_cookie_consent", lambda: True)
    panel.cookies_toggle.set_checked(True)
    assert mock_config.get("cookies_enabled") is True
    assert mock_config.get("cookies_consent_accepted") is True
