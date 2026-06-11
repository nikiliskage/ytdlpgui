"""Add-to-queue creates a dock item; a Progress update moves the ring."""

from __future__ import annotations

from app.core import contracts as c


def _load(window):  # type: ignore[no-untyped-def]
    window.omni.input.setText("https://youtube.com/watch?v=abc")
    window.omni.fetch_btn.click()


def test_add_to_queue_creates_dock_item(window, mock_runner_factory) -> None:  # type: ignore[no-untyped-def]
    _load(window)
    window.media_card.queue_btn.click()
    assert len(mock_runner_factory.created) == 1
    assert mock_runner_factory.created[0].started
    # one dock item exists
    assert len(window.dock._items) == 1  # noqa: SLF001


def test_progress_update_moves_ring(window, mock_runner_factory) -> None:  # type: ignore[no-untyped-def]
    _load(window)
    window.media_card.queue_btn.click()
    runner = mock_runner_factory.created[0]
    job_id = next(iter(window.dock._items))  # noqa: SLF001
    ring = window.dock._items[job_id].ring  # noqa: SLF001
    runner.emit_progress(c.Progress(downloaded_bytes=50, total_bytes=100))
    assert ring.percent() == 50.0


def test_finished_sets_done_state(window, mock_runner_factory) -> None:  # type: ignore[no-untyped-def]
    _load(window)
    window.media_card.queue_btn.click()
    runner = mock_runner_factory.created[0]
    job_id = next(iter(window.dock._items))  # noqa: SLF001
    runner.finish(c.JobState.COMPLETED)
    assert window.dock._items[job_id].ring.state() == c.JobState.COMPLETED  # noqa: SLF001
