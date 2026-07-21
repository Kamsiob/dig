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


class Job(QRunnable):
    """One piece of work, with its result handed back on the main thread."""

    def __init__(self, work: Callable[[], Any]):
        super().__init__()
        self._work = work
        self.signals = _Signals()

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
    job.signals.done.connect(on_done)
    if on_failed is not None:
        job.signals.failed.connect(on_failed)
    QThreadPool.globalInstance().start(job)
    return job


def wait_for_disk_work(timeout_ms: int = 5000) -> bool:
    """Block until queued work finishes. For tests and for closing down."""
    return QThreadPool.globalInstance().waitForDone(timeout_ms)
