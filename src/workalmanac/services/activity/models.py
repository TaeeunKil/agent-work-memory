from datetime import datetime
from enum import StrEnum

from workalmanac.core import WorkAlmanacModel


class ActivityTask(StrEnum):
    SYNC = "sync"
    AUTO_DISTILL = "auto-distill"


class ActivityStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"


class ActivityRun(WorkAlmanacModel):
    activity_id: str
    task: ActivityTask
    status: ActivityStatus
    started_at: datetime
    finished_at: datetime | None = None
    exit_code: int | None = None
    process_id: int
    summary: str
    log_lines: tuple[str, ...] = ()


class ActivityLedger(WorkAlmanacModel):
    runs: tuple[ActivityRun, ...] = ()
