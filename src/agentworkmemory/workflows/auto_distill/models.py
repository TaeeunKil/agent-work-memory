from enum import StrEnum

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.distillation.models import DistillReceipt


class AutoDistillRunState(StrEnum):
    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    GRANT_EXHAUSTED = "grant-exhausted"
    DISTILLATION_RUNNING = "distillation-running"
    SYNC_WAIT_EXPIRED = "sync-wait-expired"


class AutoDistillRunReceipt(AgentWorkMemoryModel):
    state: AutoDistillRunState
    session_ids: tuple[str, ...] = ()
    distill: DistillReceipt | None = None
