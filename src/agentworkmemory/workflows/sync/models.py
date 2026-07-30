from pathlib import Path

from pydantic import field_validator

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.sessions.models import AgentProviderId


class SyncAgentRecords(AgentWorkMemoryModel):
    providers: tuple[AgentProviderId, ...]
    home: Path
    include_content: bool = False

    @field_validator("providers")
    @classmethod
    def selected_providers(
        cls,
        value: tuple[AgentProviderId, ...],
    ) -> tuple[AgentProviderId, ...]:
        providers = tuple(dict.fromkeys(value))
        if not providers:
            raise ValueError("sync needs at least one provider")
        return providers
