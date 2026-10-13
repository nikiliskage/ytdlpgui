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


def test_concurrency_limit_and_slot_refill(window, mock_runner_factory, mock_config) -> None:  # type: ignore[no-untyped-def]
    """Only max_concurrent_downloads run at once; a finished job frees its slot."""
    mock_config.set("max_concurrent_downloads", 2)
    _load(window)
    for _ in range(3):
        window.media_card.queue_btn.click()
    assert len(mock_runner_factory.created) == 2

    mock_runner_factory.created[0].finish(c.JobState.COMPLETED)
    assert len(mock_runner_factory.created) == 3
    assert mock_runner_factory.created[2].started


def test_cancel_queued_job_never_starts(window, mock_runner_factory, mock_config) -> None:  # type: ignore[no-untyped-def]
    mock_config.set("max_concurrent_downloads", 1)
    _load(window)
    window.media_card.queue_btn.click()
    window.media_card.queue_btn.click()
    queued_id = window.dock.job_ids(c.JobState.QUEUED)[0]

    window._cancel_job(queued_id)  # noqa: SLF001
    mock_runner_factory.created[0].finish(c.JobState.COMPLETED)

    assert len(mock_runner_factory.created) == 1
    assert window.dock.job_ids(c.JobState.CANCELED) == [queued_id]


def test_clear_completed_removes_only_completed(window, mock_runner_factory) -> None:  # type: ignore[no-untyped-def]
    _load(window)
    window.media_card.queue_btn.click()
    window.media_card.queue_btn.click()
    mock_runner_factory.created[0].finish(c.JobState.COMPLETED)

    window._clear_completed()  # noqa: SLF001

    assert len(window.dock.job_ids()) == 1
    assert window.dock.job_ids(c.JobState.RUNNING)


def _completed_with_file(window, mock_runner_factory, path):  # type: ignore[no-untyped-def]
    _load(window)
    window.media_card.queue_btn.click()
    runner = mock_runner_factory.created[-1]
    runner.outputs = [path]
    runner.finish(c.JobState.COMPLETED)
    job_id = window.dock.job_ids()[-1]
    return window.queue_panel.row(job_id)


def test_rename_completed_download(window, mock_runner_factory, tmp_path) -> None:  # type: ignore[no-untyped-def]
    media = tmp_path / "Sample Video.mp4"
    media.write_text("x")
    row = _completed_with_file(window, mock_runner_factory, media)
    assert row.output_name() == "Sample Video"

    row.begin_rename()
    assert row.is_renaming()
    row._name_edit.setText("Renamed")  # noqa: SLF001
    row._name_edit.returnPressed.emit()  # noqa: SLF001

    assert (tmp_path / "Renamed.mp4").is_file()
    assert not media.exists()
    assert row.output_name() == "Renamed"
    assert not row.is_renaming()


def test_rename_clash_shows_inline_error(window, mock_runner_factory, tmp_path) -> None:  # type: ignore[no-untyped-def]
    media = tmp_path / "A.mp4"
    media.write_text("x")
    (tmp_path / "B.mp4").write_text("taken")
    row = _completed_with_file(window, mock_runner_factory, media)

    row.rename.emit(row.job_id, "B")

    assert media.is_file()
    assert "already exists" in row.meta_text()
    assert row.output_name() == "A"


def test_rename_hidden_without_known_output(window, mock_runner_factory) -> None:  # type: ignore[no-untyped-def]
    _load(window)
    window.media_card.queue_btn.click()
    mock_runner_factory.created[0].finish(c.JobState.COMPLETED)  # no output path
    row = window.queue_panel.row(window.dock.job_ids()[0])
    assert row.output_name() is None


def test_dock_rename_opens_queue_and_edits_row(window, mock_runner_factory, tmp_path) -> None:  # type: ignore[no-untyped-def]
    media = tmp_path / "Song.mp3"
    media.write_text("x")
    row = _completed_with_file(window, mock_runner_factory, media)
    job_id = row.job_id
    assert job_id in window.dock._renamable  # noqa: SLF001

    window.dock.rename_requested.emit(job_id)

    assert window.queue_panel.is_open()
    assert row.is_renaming()


def test_long_error_does_not_widen_the_queue(qtbot) -> None:  # type: ignore[no-untyped-def]
    """A long failure message is shortened, never forcing the list to scroll sideways."""
    from app.core.errors import map_stderr
    from app.widgets.queue_panel import QueuePanel
    from PySide6.QtWidgets import QScrollArea

    panel = QueuePanel(reduced_motion=True)
    qtbot.addWidget(panel)
    panel.resize(700, 380)
    panel.set_open(True)
    err = map_stderr("ERROR: unable to download video data: HTTP Error 403: Forbidden")
    row = panel.add_row("x", "A very long track title " * 8)
    row.set_state(c.JobState.FAILED, err.user_message, err.raw)
    qtbot.wait(20)

    assert row.minimumSizeHint().width() < 700
    assert panel.findChildren(QScrollArea)[0].horizontalScrollBar().maximum() == 0
    assert err.user_message in row.meta_text()  # full text kept (tooltip / accessor)


def test_rename_of_vanished_file_disables_rename(window, mock_runner_factory, tmp_path) -> None:  # type: ignore[no-untyped-def]
    media = tmp_path / "Gone.mp4"
    media.write_text("x")
    row = _completed_with_file(window, mock_runner_factory, media)
    media.unlink()

    row.rename.emit(row.job_id, "Other")

    assert "moved or deleted" in row.meta_text()
    assert row.output_name() is None
    assert row.job_id not in window.dock._renamable  # noqa: SLF001


def _two_failed_one_done(window, mock_runner_factory, mock_config):  # type: ignore[no-untyped-def]
    mock_config.set("max_concurrent_downloads", 3)
    _load(window)
    for _ in range(3):
        window.media_card.queue_btn.click()
    first, second, third = mock_runner_factory.created
    first.finish(c.JobState.FAILED)
    second.finish(c.JobState.COMPLETED)
    third.finish(c.JobState.FAILED)


def test_retry_failed_requeues_only_failed_jobs(window, mock_runner_factory, mock_config) -> None:  # type: ignore[no-untyped-def]
    _two_failed_one_done(window, mock_runner_factory, mock_config)

    window.queue_panel.retry_failed_btn.click()

    assert len(mock_runner_factory.created) == 5  # two new runners, one per failed job
    assert not window.dock.job_ids(c.JobState.FAILED)
    assert len(window.dock.job_ids(c.JobState.COMPLETED)) == 1


def test_clear_failed_removes_only_failed_jobs(window, mock_runner_factory, mock_config) -> None:  # type: ignore[no-untyped-def]
    _two_failed_one_done(window, mock_runner_factory, mock_config)

    window.queue_panel.clear_failed_btn.click()

    assert window.dock.job_ids() == window.dock.job_ids(c.JobState.COMPLETED)
    assert len(window.queue_panel.rows()) == 1
