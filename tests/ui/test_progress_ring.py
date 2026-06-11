"""Unit tests for the progress ring color helper and no-raise paintEvent."""

from __future__ import annotations

from app.core import contracts as c
from app.widgets.progress_ring import ProgressRing, ring_color


def test_ring_color_states() -> None:
    assert ring_color(c.JobState.RUNNING) == "#a855f7"
    assert ring_color(c.JobState.QUEUED) == "#a855f7"
    assert ring_color(c.JobState.COMPLETED) == "#3ecf8e"
    assert ring_color(c.JobState.FAILED) == "#ff5470"
    assert ring_color(c.JobState.CANCELED) == "#ff5470"


def test_paint_does_not_raise_on_boundaries(qtbot) -> None:  # type: ignore[no-untyped-def]
    ring = ProgressRing(reduced_motion=True)
    qtbot.addWidget(ring)
    for pct in (None, 0.0, 100.0):
        ring.set_percent(pct)
        ring.repaint()  # forces paintEvent; must not raise
    assert ring.percent() == 100.0


def test_set_state_updates_state(qtbot) -> None:  # type: ignore[no-untyped-def]
    ring = ProgressRing(reduced_motion=True)
    qtbot.addWidget(ring)
    ring.set_state(c.JobState.COMPLETED)
    ring.repaint()
    assert ring.state() == c.JobState.COMPLETED
