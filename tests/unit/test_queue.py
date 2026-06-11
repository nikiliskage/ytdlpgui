"""Tests for QueueManager (Stream C).

All tests are deterministic — runner callbacks are triggered manually via
MockRunner.finish() / emit_progress(), so no real event-loop is needed.
"""

from __future__ import annotations

import pytest
from app.core.contracts import AppError, DownloadOptions, ErrorKind, JobState, Progress
from app.core.queue_manager import QueueManager
from PySide6.QtCore import QCoreApplication

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_options(url: str = "https://example.com/video", **kwargs: object) -> DownloadOptions:
    return DownloadOptions(url=url, **kwargs)  # type: ignore[arg-type]


# Ensure a QCoreApplication exists so QObject / Signal work without a full
# Qt event loop.
@pytest.fixture(scope="session", autouse=True)
def _qt_app() -> QCoreApplication:
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Test 1 — max_concurrent=2, four jobs; exactly 2 RUNNING; finish one → 3rd starts
# ---------------------------------------------------------------------------


def test_max_concurrent_two(mock_runner_factory):  # type: ignore[no-untyped-def]
    qm = QueueManager(runner_factory=mock_runner_factory, max_concurrent=2)

    opts = [make_options(f"https://example.com/{i}") for i in range(4)]
    ids = [qm.add(o) for o in opts]

    # After adding 4 jobs only 2 should be running.
    running = [j for j in qm.jobs() if j.state == JobState.RUNNING]
    queued = [j for j in qm.jobs() if j.state == JobState.QUEUED]
    assert len(running) == 2, f"Expected 2 running, got {len(running)}"
    assert len(queued) == 2, f"Expected 2 queued, got {len(queued)}"
    assert len(mock_runner_factory.created) == 2

    # Finish the first running job — the 3rd job should start.
    first_runner = mock_runner_factory.created[0]
    first_runner.finish(JobState.COMPLETED)

    running_after = [j for j in qm.jobs() if j.state == JobState.RUNNING]
    assert len(running_after) == 2, f"Expected 2 running after finish, got {len(running_after)}"
    assert len(mock_runner_factory.created) == 3

    # The first job should now be COMPLETED.
    assert qm.get_job(ids[0]).state == JobState.COMPLETED  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Test 2 — max_concurrent=1; strictly one at a time
# ---------------------------------------------------------------------------


def test_max_concurrent_one(mock_runner_factory):  # type: ignore[no-untyped-def]
    qm = QueueManager(runner_factory=mock_runner_factory, max_concurrent=1)

    ids = [qm.add(make_options(f"https://example.com/{i}")) for i in range(3)]

    # Only 1 running.
    running = [j for j in qm.jobs() if j.state == JobState.RUNNING]
    queued = [j for j in qm.jobs() if j.state == JobState.QUEUED]
    assert len(running) == 1
    assert len(queued) == 2
    assert len(mock_runner_factory.created) == 1

    # Finish the first — second starts.
    mock_runner_factory.created[0].finish(JobState.COMPLETED)
    running = [j for j in qm.jobs() if j.state == JobState.RUNNING]
    assert len(running) == 1
    assert len(mock_runner_factory.created) == 2

    # Finish the second — third starts.
    mock_runner_factory.created[1].finish(JobState.COMPLETED)
    running = [j for j in qm.jobs() if j.state == JobState.RUNNING]
    assert len(running) == 1
    assert len(mock_runner_factory.created) == 3

    # Finish last — queue empty / all completed.
    mock_runner_factory.created[2].finish(JobState.COMPLETED)
    running = [j for j in qm.jobs() if j.state == JobState.RUNNING]
    assert len(running) == 0
    for jid in ids:
        assert qm.get_job(jid).state == JobState.COMPLETED  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Test 3 — middle job FAILED; queue continues; retry re-queues and runs it
# ---------------------------------------------------------------------------


def test_failed_job_and_retry(mock_runner_factory):  # type: ignore[no-untyped-def]
    qm = QueueManager(runner_factory=mock_runner_factory, max_concurrent=2)

    ids = [qm.add(make_options(f"https://example.com/{i}")) for i in range(3)]
    # Jobs 0 and 1 are RUNNING, job 2 is QUEUED.

    # Fail job 1 (second runner).
    error = AppError(kind=ErrorKind.NETWORK, user_message="Network error")
    mock_runner_factory.created[1].finish(JobState.FAILED, error)

    job1 = qm.get_job(ids[1])
    assert job1 is not None
    assert job1.state == JobState.FAILED
    assert job1.error is not None

    # Job 2 should have started to fill the slot.
    running = [j for j in qm.jobs() if j.state == JobState.RUNNING]
    assert len(running) == 2

    # Retry job 1 — it goes back to QUEUED (no slot available right now).
    qm.retry(ids[1])
    assert job1.state == JobState.QUEUED

    # Finish job 0 → job 1 (retried) starts.
    mock_runner_factory.created[0].finish(JobState.COMPLETED)
    assert job1.state == JobState.RUNNING

    # Finish the remaining two.
    mock_runner_factory.created[2].finish(JobState.COMPLETED)
    mock_runner_factory.created[3].finish(JobState.COMPLETED)  # retried job 1

    assert all(j.state == JobState.COMPLETED for j in qm.jobs())


# ---------------------------------------------------------------------------
# Test 4 — cancel a RUNNING job; a waiting job starts
# ---------------------------------------------------------------------------


def test_cancel_running_job(mock_runner_factory):  # type: ignore[no-untyped-def]
    qm = QueueManager(runner_factory=mock_runner_factory, max_concurrent=2)

    ids = [qm.add(make_options(f"https://example.com/{i}")) for i in range(3)]
    # Jobs 0, 1 RUNNING; job 2 QUEUED.

    qm.cancel(ids[0])

    job0 = qm.get_job(ids[0])
    assert job0 is not None
    assert job0.state == JobState.CANCELED
    # The runner's cancel() should have been called.
    assert mock_runner_factory.created[0].canceled is True

    # Job 2 should have started.
    job2 = qm.get_job(ids[2])
    assert job2 is not None
    assert job2.state == JobState.RUNNING
    running = [j for j in qm.jobs() if j.state == JobState.RUNNING]
    assert len(running) == 2


# ---------------------------------------------------------------------------
# Test 5 — add_many adds all items to the queue
# ---------------------------------------------------------------------------


def test_add_many(mock_runner_factory):  # type: ignore[no-untyped-def]
    qm = QueueManager(runner_factory=mock_runner_factory, max_concurrent=2)

    playlist = [make_options(f"https://example.com/playlist/{i}") for i in range(5)]
    ids = qm.add_many(playlist)

    assert len(ids) == 5
    assert len(qm.jobs()) == 5
    # Exactly max_concurrent should be running.
    running = [j for j in qm.jobs() if j.state == JobState.RUNNING]
    queued = [j for j in qm.jobs() if j.state == JobState.QUEUED]
    assert len(running) == 2
    assert len(queued) == 3
    assert len(mock_runner_factory.created) == 2


# ---------------------------------------------------------------------------
# Test 6 — progress propagation
# ---------------------------------------------------------------------------


def test_progress_propagation(mock_runner_factory):  # type: ignore[no-untyped-def]
    qm = QueueManager(runner_factory=mock_runner_factory, max_concurrent=1)
    job_id = qm.add(make_options())

    progress = Progress(downloaded_bytes=500, total_bytes=1000)
    mock_runner_factory.created[0].emit_progress(progress)

    job = qm.get_job(job_id)
    assert job is not None
    assert job.progress.downloaded_bytes == 500
    assert job.progress.total_bytes == 1000


# ---------------------------------------------------------------------------
# Test 7 — queue_finished signal fires when all jobs are terminal
# ---------------------------------------------------------------------------


def test_queue_finished_signal(mock_runner_factory):  # type: ignore[no-untyped-def]
    finished_calls: list[None] = []
    qm = QueueManager(runner_factory=mock_runner_factory, max_concurrent=2)
    qm.queue_finished.connect(lambda: finished_calls.append(None))

    for i in range(2):
        qm.add(make_options(f"https://example.com/{i}"))

    mock_runner_factory.created[0].finish(JobState.COMPLETED)
    assert len(finished_calls) == 0  # still one running

    mock_runner_factory.created[1].finish(JobState.COMPLETED)
    assert len(finished_calls) == 1


# ---------------------------------------------------------------------------
# Test 8 — cancel a QUEUED (not yet started) job
# ---------------------------------------------------------------------------


def test_cancel_queued_job(mock_runner_factory):  # type: ignore[no-untyped-def]
    qm = QueueManager(runner_factory=mock_runner_factory, max_concurrent=1)

    ids = [qm.add(make_options(f"https://example.com/{i}")) for i in range(2)]
    # Job 0 RUNNING, job 1 QUEUED.

    qm.cancel(ids[1])
    job1 = qm.get_job(ids[1])
    assert job1 is not None
    assert job1.state == JobState.CANCELED
    # No extra runner should have been created.
    assert len(mock_runner_factory.created) == 1


# ---------------------------------------------------------------------------
# Test 9 — clear_finished removes only terminal jobs
# ---------------------------------------------------------------------------


def test_clear_finished(mock_runner_factory):  # type: ignore[no-untyped-def]
    qm = QueueManager(runner_factory=mock_runner_factory, max_concurrent=2)

    ids = [qm.add(make_options(f"https://example.com/{i}")) for i in range(3)]
    mock_runner_factory.created[0].finish(JobState.COMPLETED)

    qm.clear_finished()
    remaining = qm.jobs()
    assert len(remaining) == 2
    assert all(j.id != ids[0] for j in remaining)
