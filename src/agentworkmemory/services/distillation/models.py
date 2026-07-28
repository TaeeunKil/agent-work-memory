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


class SessionDistillDisposition(StrEnum):
    CREATED = "created"
    MERGED = "merged"
    ALREADY_COVERED = "already-covered"
    NO_DURABLE_KNOWLEDGE = "no-durable-knowledge"


class SessionDistillOutcome(AgentWorkMemoryModel):
    session_id: str
    disposition: SessionDistillDisposition
    reason: str
    pages: tuple[Path, ...] = ()


class DistillReceipt(AgentWorkMemoryModel):
    run_id: str
    runtime: str
    model: str | None
    content_access: ContentAccess
    session_ids: tuple[str, ...]
    status: DistillStatus
    changed_files: tuple[Path, ...] = ()
    session_outcomes: tuple[SessionDistillOutcome, ...] = ()
    output_summary: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
