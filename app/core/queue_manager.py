"""Download queue manager (Stream C).

Manages a bounded pool of concurrent yt-dlp downloads via injected
RunnerFactory. Talks to runners only through IYtDlpRunner.set_callbacks /
start / cancel — no real subprocesses.

Design patterns used:
- Command: DownloadJob encapsulates a single download request + its lifecycle.
- State: JobState drives transitions (QUEUED → RUNNING → terminal).
- Observer: Qt signals (job_added, job_updated, queue_finished) notify UI.
- Factory injection: max_concurrent runners created on-demand via RunnerFactory.
"""

from __future__ import annotations

import uuid

from PySide6.QtCore import QObject, Signal

from app.core.contracts import (
    AppError,
    DownloadOptions,
    IYtDlpRunner,
    JobState,
    Progress,
    RunnerFactory,
)

# ---------------------------------------------------------------------------
# DownloadJob — Command object
# ---------------------------------------------------------------------------


class DownloadJob:
    """Represents a single enqueued download (Command pattern).

    Attributes:
        id: Unique identifier (UUID4 string).
        options: All download parameters.
        state: Current lifecycle state.
        progress: Latest progress snapshot.
        error: Set on FAILED; None otherwise.
        title: Human-readable label (derived from URL by default).
    """

    def __init__(self, options: DownloadOptions) -> None:
        self.id: str = uuid.uuid4().hex
        self.options: DownloadOptions = options
        self.state: JobState = JobState.QUEUED
        self.progress: Progress = Progress()
        self.error: AppError | None = None
        self.title: str = options.url

    def __repr__(self) -> str:
        return f"DownloadJob(id={self.id[:8]}, state={self.state}, url={self.options.url!r})"


# ---------------------------------------------------------------------------
# QueueManager — Observer + State machine
# ---------------------------------------------------------------------------


class QueueManager(QObject):
    """Manages a bounded pool of concurrent yt-dlp downloads.

    Args:
        runner_factory: Callable that returns a fresh IYtDlpRunner instance.
        max_concurrent: Maximum number of jobs allowed in RUNNING state.

    Signals:
        job_added(str): Emitted when a new job enters the queue.
        job_updated(str): Emitted whenever a job's state/progress changes.
        queue_finished(): Emitted when all jobs reach a terminal state.
    """

    job_added = Signal(str)
    job_updated = Signal(str)
    queue_finished = Signal()

    def __init__(
        self,
        runner_factory: RunnerFactory,
        max_concurrent: int = 2,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._factory: RunnerFactory = runner_factory
        self._max_concurrent: int = max_concurrent

        # Ordered list of all jobs (preserves insertion order).
        self._jobs: list[DownloadJob] = []
        # Maps job_id → active runner (only for RUNNING jobs).
        self._runners: dict[str, IYtDlpRunner] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, options: DownloadOptions) -> str:
        """Enqueue a single download job.

        Returns:
            The new job's id.
        """
        job = DownloadJob(options)
        self._jobs.append(job)
        self.job_added.emit(job.id)
        self._schedule()
        return job.id

    def add_many(self, options_list: list[DownloadOptions]) -> list[str]:
        """Enqueue multiple downloads at once (e.g. playlist items).

        Returns:
            List of new job ids in insertion order.
        """
        ids: list[str] = []
        for opts in options_list:
            job = DownloadJob(opts)
            self._jobs.append(job)
            ids.append(job.id)
            self.job_added.emit(job.id)
        self._schedule()
        return ids

    def remove(self, job_id: str) -> None:
        """Remove a job from the queue.

        Only non-running (QUEUED or terminal) jobs may be removed. Running
        jobs must be cancelled first.
        """
        job = self._get_job(job_id)
        if job is None:
            return
        if job.state == JobState.RUNNING:
            # Safety: cancel before removing so the runner is cleaned up.
            self.cancel(job_id)
        self._jobs = [j for j in self._jobs if j.id != job_id]

    def cancel(self, job_id: str) -> None:
        """Cancel a RUNNING or QUEUED job.

        For a running job the underlying runner is cancelled, the job
        transitions to CANCELED, and the freed slot is filled immediately.
        """
        job = self._get_job(job_id)
        if job is None:
            return
        if job.state == JobState.QUEUED:
            job.state = JobState.CANCELED
            self.job_updated.emit(job_id)
            self._check_queue_finished()
            return
        if job.state == JobState.RUNNING:
            runner = self._runners.pop(job_id, None)
            if runner is not None:
                runner.cancel()
            job.state = JobState.CANCELED
            self.job_updated.emit(job_id)
            # Fill the freed slot.
            self._schedule()
            self._check_queue_finished()

    def retry(self, job_id: str) -> None:
        """Re-queue a FAILED or CANCELED job.

        Resets the job to QUEUED and triggers scheduling so it can start
        immediately if a slot is available.
        """
        job = self._get_job(job_id)
        if job is None:
            return
        if job.state not in (JobState.FAILED, JobState.CANCELED):
            return
        job.state = JobState.QUEUED
        job.progress = Progress()
        job.error = None
        self.job_updated.emit(job_id)
        self._schedule()

    def clear_finished(self) -> None:
        """Remove all jobs in a terminal state from the queue."""
        self._jobs = [j for j in self._jobs if not j.state.is_terminal]

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def jobs(self) -> list[DownloadJob]:
        """Return a snapshot of all jobs (insertion order)."""
        return list(self._jobs)

    def get_job(self, job_id: str) -> DownloadJob | None:
        """Return the job with the given id, or None."""
        return self._get_job(job_id)

    # ------------------------------------------------------------------
    # Internal scheduling
    # ------------------------------------------------------------------

    def _running_count(self) -> int:
        return sum(1 for j in self._jobs if j.state == JobState.RUNNING)

    def _schedule(self) -> None:
        """Start as many QUEUED jobs as free slots allow."""
        while self._running_count() < self._max_concurrent:
            next_job = self._next_queued()
            if next_job is None:
                break
            self._start_job(next_job)

    def _next_queued(self) -> DownloadJob | None:
        for job in self._jobs:
            if job.state == JobState.QUEUED:
                return job
        return None

    def _start_job(self, job: DownloadJob) -> None:
        runner = self._factory()
        job.state = JobState.RUNNING
        self._runners[job.id] = runner

        # Capture job_id in closure for the callbacks.
        job_id = job.id

        def on_progress(progress: Progress) -> None:
            j = self._get_job(job_id)
            if j is not None:
                j.progress = progress
                self.job_updated.emit(job_id)

        def on_log(_line: str) -> None:
            # Log lines are forwarded silently for now; UI can connect.
            pass

        def on_finished(state: JobState, error: AppError | None) -> None:
            j = self._get_job(job_id)
            if j is None:
                return
            # Only update state if the job is still running (not cancelled).
            if j.state == JobState.RUNNING:
                j.state = state
                j.error = error
            self._runners.pop(job_id, None)
            self.job_updated.emit(job_id)
            self._schedule()
            self._check_queue_finished()

        runner.set_callbacks(on_progress, on_log, on_finished)
        runner.start(job.options)
        self.job_updated.emit(job.id)

    def _get_job(self, job_id: str) -> DownloadJob | None:
        for job in self._jobs:
            if job.id == job_id:
                return job
        return None

    def _check_queue_finished(self) -> None:
        """Emit queue_finished when every job has reached a terminal state."""
        if not self._jobs:
            return
        if all(j.state.is_terminal for j in self._jobs):
            self.queue_finished.emit()
