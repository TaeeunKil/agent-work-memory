from datetime import datetime
from enum import StrEnum

from workalmanac.core import WorkAlmanacModel
from workalmanac.services.sessions.models import AgentProviderId


class SyncStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    SKIPPED_LOCKED = "skipped_locked"
    FAILED = "failed"


class SyncReceipt(WorkAlmanacModel):
    run_id: str
    providers: tuple[AgentProviderId, ...]
    include_content: bool
    status: SyncStatus
    sessions_discovered: int = 0
    sessions_updated: int = 0
    events_added: int = 0
    error_type: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
