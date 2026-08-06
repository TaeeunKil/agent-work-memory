from pydantic import field_validator

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.curators.models import ContentAccess, ReasoningEffort


class DistillSessions(AgentWorkMemoryModel):
    session_ids: tuple[str, ...]
    runtime: str
    model: str | None = None
    effort: ReasoningEffort | None = None
    content_access: ContentAccess = ContentAccess.METADATA_ONLY

    @field_validator("session_ids")
    @classmethod
    def require_sessions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        session_ids = tuple(
            dict.fromkeys(item.strip() for item in value if item.strip())
        )
        if not session_ids:
            raise ValueError("distill requires at least one session id")
        return session_ids

    @field_validator("runtime")
    @classmethod
    def require_runtime(cls, value: str) -> str:
        runtime = value.strip()
        if not runtime:
            raise ValueError("distill runtime must not be empty")
        return runtime
