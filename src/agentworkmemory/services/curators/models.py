from enum import StrEnum
from pathlib import Path

from pydantic import field_validator

from agentworkmemory.core import AgentWorkMemoryModel


class ContentAccess(StrEnum):
    METADATA_ONLY = "metadata-only"
    SELECTED_LOCAL = "selected-local"
    SELECTED_REMOTE = "selected-remote"


class ReasoningEffort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


class CuratorRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CuratorReadiness(AgentWorkMemoryModel):
    runtime: str
    available: bool
    message: str
    repair: str | None = None


class CuratorRunRequest(AgentWorkMemoryModel):
    runtime: str
    model: str | None = None
    effort: ReasoningEffort | None = None
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


class CuratorRunResult(AgentWorkMemoryModel):
    runtime: str
    status: CuratorRunStatus
    output_text: str
    provider_session_id: str | None = None
