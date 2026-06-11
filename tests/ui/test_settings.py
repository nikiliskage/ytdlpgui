"""Settings change writes to the injected config; cookie toggle reveals note."""

from __future__ import annotations

from app.widgets.settings_panel import SettingsPanel


def test_setting_change_writes_to_config(qtbot, mock_config) -> None:  # type: ignore[no-untyped-def]
    panel = SettingsPanel(mock_config, reduced_motion=True)
    qtbot.addWidget(panel)
    panel.audio_pills.select("mp3")
    assert mock_config.get("audio_format") == "mp3"
    assert mock_config.saved > 0


def test_slider_writes_max_concurrent(qtbot, mock_config) -> None:  # type: ignore[no-untyped-def]
    panel = SettingsPanel(mock_config, reduced_motion=True)
    qtbot.addWidget(panel)
    panel.max_downloads.setValue(4)
    assert mock_config.get("max_concurrent_downloads") == 4


def test_cookie_toggle_reveals_note(qtbot, mock_config) -> None:  # type: ignore[no-untyped-def]
    panel = SettingsPanel(mock_config, reduced_motion=True)
    qtbot.addWidget(panel)
    panel.show()
    assert not panel._note.isVisible()  # noqa: SLF001
    panel.cookies_toggle.set_checked(True)
    assert panel._note.isVisible()  # noqa: SLF001
    assert mock_config.get("cookies_enabled") is True
