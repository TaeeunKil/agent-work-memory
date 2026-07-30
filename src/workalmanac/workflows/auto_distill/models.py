from enum import StrEnum

from workalmanac.core import WorkAlmanacModel
from workalmanac.services.distillation.models import DistillReceipt


class AutoDistillRunState(StrEnum):
    SUCCEEDED = "succeeded"
    EMPTY = "empty"
    GRANT_EXHAUSTED = "grant-exhausted"
    SKIPPED_LOCKED = "skipped-locked"


class AutoDistillRunReceipt(WorkAlmanacModel):
    state: AutoDistillRunState
    session_ids: tuple[str, ...] = ()
    distill: DistillReceipt | None = None
