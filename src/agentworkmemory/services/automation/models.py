from datetime import datetime
from pathlib import Path

from pydantic import Field, field_validator

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.sessions.models import AgentProviderId


class AutoSyncSettings(AgentWorkMemoryModel):
    interval_minutes: int = Field(ge=1, le=1439)
    providers: tuple[AgentProviderId, ...]
    home: Path
    include_content: bool = False
    installed_at: datetime | None = None

    @field_validator("providers")
    @classmethod
    def selected_providers(
        cls,
        value: tuple[AgentProviderId, ...],
    ) -> tuple[AgentProviderId, ...]:
        providers = tuple(dict.fromkeys(value))
        if not providers:
            raise ValueError("automatic sync needs at least one provider")
        return providers


class SchedulerStatus(AgentWorkMemoryModel):
    available: bool
    installed: bool
    task_name: str
    message: str
    settings: AutoSyncSettings | None = None
    next_run_at: datetime | None = None
