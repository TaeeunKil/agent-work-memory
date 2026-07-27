from enum import StrEnum
from pathlib import Path

from pydantic import field_validator

from workalmanac.core import WorkAlmanacModel


class ContentAccess(StrEnum):
    METADATA_ONLY = "metadata-only"
    SELECTED_LOCAL = "selected-local"
    SELECTED_REMOTE = "selected-remote"


class CuratorRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CuratorReadiness(WorkAlmanacModel):
    runtime: str
    available: bool
    message: str
    repair: str | None = None


class CuratorRunRequest(WorkAlmanacModel):
    runtime: str
    model: str | None = None
    vault_path: Path
    prompt: str
    content_access: ContentAccess

    @field_validator("runtime", "prompt")
    @classmethod
    def require_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("curator request text must not be empty")
        return text


class CuratorRunResult(WorkAlmanacModel):
    runtime: str
    status: CuratorRunStatus
    output_text: str
    provider_session_id: str | None = None
