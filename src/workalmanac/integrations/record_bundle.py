from datetime import datetime
from pathlib import Path

from pydantic import field_validator

from workalmanac.core import WorkAlmanacModel
from workalmanac.services.sessions.models import (
    AgentEventKind,
    AgentProviderId,
)


class ImportedAgentEvent(WorkAlmanacModel):
    kind: AgentEventKind = AgentEventKind.MESSAGE
    role: str | None = None
    label: str | None = None
    occurred_at: datetime | None = None
    content: str

    @field_validator("content")
    @classmethod
    def require_content(cls, value: str) -> str:
        content = value.strip()
        if not content:
            raise ValueError("imported event content must not be empty")
        return content


class AgentRecordBundle(WorkAlmanacModel):
    provider: AgentProviderId
    session_id: str
    title: str | None = None
    cwd: Path | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    events: tuple[ImportedAgentEvent, ...]

    @field_validator("session_id")
    @classmethod
    def require_session_id(cls, value: str) -> str:
        session_id = value.strip()
        if not session_id:
            raise ValueError("imported session id must not be empty")
        return session_id


def load_record_bundle(path: Path) -> AgentRecordBundle:
    return AgentRecordBundle.model_validate_json(path.read_text(encoding="utf-8"))
