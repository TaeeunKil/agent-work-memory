from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

DEFAULT_SYNC_WAIT_SECONDS = 10 * 60


class DistillationAlreadyRunning(RuntimeError):
    pass


class SynchronizationWaitExpired(RuntimeError):
    pass


class DistillCoordination:
    def __init__(self, distill_lock_path: Path, sync_lock_path: Path):
        self.distill_lock_path = distill_lock_path
        self.sync_lock_path = sync_lock_path

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        lock = FileLock(self.distill_lock_path)
        try:
            lock.acquire(timeout=0)
        except Timeout as error:
            raise DistillationAlreadyRunning from error
        try:
            yield
        finally:
            lock.release()

    @contextmanager
    def after_synchronization(
        self,
        progress: Callable[[str], None] | None = None,
        *,
        wait_seconds: float = DEFAULT_SYNC_WAIT_SECONDS,
    ) -> Iterator[None]:
        lock = FileLock(self.sync_lock_path)
        try:
            lock.acquire(timeout=0)
        except Timeout:
            wait_minutes = max(1, round(wait_seconds / 60))
            report_progress(
                progress,
                "Synchronization is running. "
                f"Waiting up to {wait_minutes} minute(s) before distillation.",
            )
            try:
                lock.acquire(timeout=wait_seconds)
            except Timeout as error:
                report_progress(
                    progress,
                    "Synchronization did not finish before the wait limit.",
                )
                raise SynchronizationWaitExpired from error
            report_progress(
                progress,
                "Synchronization finished. Starting Wiki distillation; "
                "this can take several minutes.",
            )
        else:
            report_progress(
                progress,
                "Starting Wiki distillation; this can take several minutes.",
            )
        try:
            yield
        finally:
            lock.release()


def report_progress(
    progress: Callable[[str], None] | None,
    message: str,
) -> None:
    if progress is not None:
        progress(message)
