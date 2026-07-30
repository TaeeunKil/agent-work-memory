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

    def run(self) -> AutoDistillRunReceipt:
        settings = self.automation.settings()
        lock = FileLock(self.lock_path, timeout=0)
        coordination_lock = FileLock(self.coordination_lock_path, timeout=0)
        try:
            with lock, coordination_lock:
                batch_limit = self.automation.available_batch_limit()
                if batch_limit == 0:
                    return AutoDistillRunReceipt(
                        state=AutoDistillRunState.GRANT_EXHAUSTED
                    )
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
        except Timeout:
            return AutoDistillRunReceipt(
                state=AutoDistillRunState.SKIPPED_LOCKED
            )
        return AutoDistillRunReceipt(
            state=AutoDistillRunState.SUCCEEDED,
            session_ids=session_ids,
            distill=receipt,
        )
