from datetime import datetime
from enum import StrEnum
from pathlib import Path

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.curators.models import ContentAccess


class DistillStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DistillReceipt(AgentWorkMemoryModel):
    run_id: str
    runtime: str
    model: str | None
    content_access: ContentAccess
    session_ids: tuple[str, ...]
    status: DistillStatus
    changed_files: tuple[Path, ...] = ()
    output_summary: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
