"""Run slow disk work off the main thread.

Copying a large screenshot in or deleting an app's folder must never freeze
the window. The control that started the work says so quietly while it runs.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


# Jobs in flight. Without a reference here, Python is free to collect the job
# and its signal object while the work is still running, and the completion
# callback is simply never delivered: the work happens and nothing reacts.
_in_flight: set[Job] = set()


class Job(QRunnable):
    """One piece of work, with its result handed back on the main thread."""

    def __init__(self, work: Callable[[], Any]):
        super().__init__()
        self._work = work
        self.signals = _Signals()
        # Lifetime is managed here, not by the thread pool, so the Python
        # object outlives the C++ one for as long as the signal needs it.
        self.setAutoDelete(False)

    @Slot()
    def run(self) -> None:
        try:
            result = self._work()
        except Exception as failure:  # noqa: BLE001 - reported, never swallowed
            self.signals.failed.emit(str(failure))
            return
        self.signals.done.emit(result)


def run_off_thread(
    work: Callable[[], Any],
    on_done: Callable[[Any], None],
    on_failed: Callable[[str], None] | None = None,
) -> Job:
    """Do `work` in the background and call `on_done` back on the main thread."""
    job = Job(work)
    _in_flight.add(job)

    def finished(result: Any) -> None:
        _in_flight.discard(job)
        on_done(result)

    def failed(message: str) -> None:
        _in_flight.discard(job)
        if on_failed is not None:
            on_failed(message)

    job.signals.done.connect(finished)
    job.signals.failed.connect(failed)
    QThreadPool.globalInstance().start(job)
    return job


def wait_for_disk_work(timeout_ms: int = 5000) -> bool:
    """Block until queued work finishes. For tests and for closing down."""
    return QThreadPool.globalInstance().waitForDone(timeout_ms)
