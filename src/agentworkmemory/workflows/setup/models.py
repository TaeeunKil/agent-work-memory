from pathlib import Path

from pydantic import Field, field_validator

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.sessions.models import (
    LOCAL_TRANSCRIPT_PROVIDERS,
    AgentProviderId,
)
from agentworkmemory.services.synchronization.models import SyncReceipt


class SetupAgentWorkMemory(AgentWorkMemoryModel):
    vault_path: Path
    home: Path
    providers: tuple[AgentProviderId, ...] = LOCAL_TRANSCRIPT_PROVIDERS
    include_content: bool = False
    auto_interval_minutes: int | None = Field(default=None, ge=1, le=1439)

    @field_validator("providers")
    @classmethod
    def selected_providers(
        cls,
        value: tuple[AgentProviderId, ...],
    ) -> tuple[AgentProviderId, ...]:
        providers = tuple(dict.fromkeys(value))
        if not providers:
            raise ValueError("setup needs at least one provider")
        return providers


class SetupAgentWorkMemoryResult(AgentWorkMemoryModel):
    vault_path: Path
    sync: SyncReceipt
    automation_installed: bool
