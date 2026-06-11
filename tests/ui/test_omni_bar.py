"""Omni-bar URL validation + Fetch enabling + Enter triggers fetch."""

from __future__ import annotations

from app.widgets.omni_bar import OmniBar
from PySide6.QtCore import Qt


def test_invalid_url_keeps_fetch_disabled(qtbot) -> None:  # type: ignore[no-untyped-def]
    bar = OmniBar(reduced_motion=True)
    qtbot.addWidget(bar)
    bar.input.setText("not a url")
    assert not bar.fetch_btn.isEnabled()


def test_valid_url_enables_fetch(qtbot) -> None:  # type: ignore[no-untyped-def]
    bar = OmniBar(reduced_motion=True)
    qtbot.addWidget(bar)
    bar.input.setText("https://youtube.com/watch?v=abc")
    assert bar.fetch_btn.isEnabled()


def test_enter_triggers_fetch_when_valid(qtbot) -> None:  # type: ignore[no-untyped-def]
    bar = OmniBar(reduced_motion=True)
    qtbot.addWidget(bar)
    received: list[str] = []
    bar.fetch_requested.connect(received.append)
    bar.input.setText("https://youtube.com/watch?v=abc")
    qtbot.keyClick(bar.input, Qt.Key.Key_Return)
    assert received == ["https://youtube.com/watch?v=abc"]


def test_enter_does_nothing_when_invalid(qtbot) -> None:  # type: ignore[no-untyped-def]
    bar = OmniBar(reduced_motion=True)
    qtbot.addWidget(bar)
    received: list[str] = []
    bar.fetch_requested.connect(received.append)
    bar.input.setText("ftp://bad")
    qtbot.keyClick(bar.input, Qt.Key.Key_Return)
    assert received == []
