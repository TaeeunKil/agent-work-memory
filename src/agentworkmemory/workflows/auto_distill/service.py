from collections.abc import Callable

from agentworkmemory.services.auto_distillation.service import (
    AutoDistillationService,
)
from agentworkmemory.services.sessions.service import SessionsService
from agentworkmemory.workflows.auto_distill.models import (
    AutoDistillRunReceipt,
    AutoDistillRunState,
)
from agentworkmemory.workflows.distill import DistillSessions, DistillSessionsWorkflow
from agentworkmemory.workflows.distill.coordination import (
    DEFAULT_SYNC_WAIT_SECONDS,
    DistillationAlreadyRunning,
    DistillCoordination,
    SynchronizationWaitExpired,
    report_progress,
)


class AutoDistillWorkflow:
    def __init__(
        self,
        automation: AutoDistillationService,
        sessions: SessionsService,
        distill: DistillSessionsWorkflow,
        coordination: DistillCoordination,
    ):
        self.automation = automation
        self.sessions = sessions
        self.distill = distill
        self.coordination = coordination

    def run(
        self,
        progress: Callable[[str], None] | None = None,
        *,
        sync_wait_seconds: float = DEFAULT_SYNC_WAIT_SECONDS,
    ) -> AutoDistillRunReceipt:
        try:
            with self.coordination.exclusive():
                settings = self.automation.settings()
                batch_limit = self.automation.available_batch_limit()
                if batch_limit == 0:
                    return AutoDistillRunReceipt(
                        state=AutoDistillRunState.GRANT_EXHAUSTED
                    )

                with self.coordination.after_synchronization(
                    progress,
                    wait_seconds=sync_wait_seconds,
                ):
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
        except DistillationAlreadyRunning:
            report_progress(
                progress,
                "Another Wiki distillation is already running.",
            )
            return AutoDistillRunReceipt(
                state=AutoDistillRunState.DISTILLATION_RUNNING
            )
        except SynchronizationWaitExpired:
            return AutoDistillRunReceipt(
                state=AutoDistillRunState.SYNC_WAIT_EXPIRED
            )

        return AutoDistillRunReceipt(
            state=AutoDistillRunState.SUCCEEDED,
            session_ids=session_ids,
            distill=receipt,
        )
