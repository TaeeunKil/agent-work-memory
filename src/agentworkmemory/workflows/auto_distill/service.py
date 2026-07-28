from collections.abc import Callable
from pathlib import Path

from filelock import FileLock, Timeout

from agentworkmemory.services.auto_distillation.service import (
    AutoDistillationService,
)
from agentworkmemory.services.sessions.service import SessionsService
from agentworkmemory.workflows.auto_distill.models import (
    AutoDistillRunReceipt,
    AutoDistillRunState,
)
from agentworkmemory.workflows.distill import DistillSessions, DistillSessionsWorkflow

DEFAULT_SYNC_WAIT_SECONDS = 10 * 60


class AutoDistillWorkflow:
    def __init__(
        self,
        automation: AutoDistillationService,
        sessions: SessionsService,
        distill: DistillSessionsWorkflow,
        lock_path: Path,
        coordination_lock_path: Path,
    ):
        self.automation = automation
        self.sessions = sessions
        self.distill = distill
        self.lock_path = lock_path
        self.coordination_lock_path = coordination_lock_path

    def run(
        self,
        progress: Callable[[str], None] | None = None,
        *,
        sync_wait_seconds: float = DEFAULT_SYNC_WAIT_SECONDS,
    ) -> AutoDistillRunReceipt:
        distill_lock = FileLock(self.lock_path)
        try:
            distill_lock.acquire(timeout=0)
        except Timeout:
            report_progress(
                progress,
                "Another Wiki distillation is already running.",
            )
            return AutoDistillRunReceipt(
                state=AutoDistillRunState.DISTILLATION_RUNNING
            )

        try:
            settings = self.automation.settings()
            batch_limit = self.automation.available_batch_limit()
            if batch_limit == 0:
                return AutoDistillRunReceipt(
                    state=AutoDistillRunState.GRANT_EXHAUSTED
                )

            coordination_lock = FileLock(self.coordination_lock_path)
            try:
                coordination_lock.acquire(timeout=0)
            except Timeout:
                wait_minutes = max(1, round(sync_wait_seconds / 60))
                report_progress(
                    progress,
                    "Synchronization is running. "
                    f"Waiting up to {wait_minutes} minute(s) before distillation.",
                )
                try:
                    coordination_lock.acquire(timeout=sync_wait_seconds)
                except Timeout:
                    report_progress(
                        progress,
                        "Synchronization did not finish before the wait limit.",
                    )
                    return AutoDistillRunReceipt(
                        state=AutoDistillRunState.SYNC_WAIT_EXPIRED
                    )
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
                session_ids = tuple(
                    session.session_id
                    for session in self.sessions.pending_distillation(
                        batch_limit
                    )
                )
                if not session_ids:
                    return AutoDistillRunReceipt(
                        state=AutoDistillRunState.EMPTY
                    )
                request = DistillSessions(
                    session_ids=session_ids,
                    runtime=settings.runtime,
                    model=settings.model,
                    content_access=settings.content_access,
                )
                self.distill.preflight(request)
                self.automation.reserve_sessions(len(session_ids))
                receipt = self.distill.run(request)
            finally:
                coordination_lock.release()
        finally:
            distill_lock.release()

        return AutoDistillRunReceipt(
            state=AutoDistillRunState.SUCCEEDED,
            session_ids=session_ids,
            distill=receipt,
        )


def report_progress(
    progress: Callable[[str], None] | None,
    message: str,
) -> None:
    if progress is not None:
        progress(message)
