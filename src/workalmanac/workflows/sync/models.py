from pathlib import Path

from pydantic import field_validator

from workalmanac.core import WorkAlmanacModel
from workalmanac.services.sessions.models import AgentProviderId


class SyncAgentRecords(WorkAlmanacModel):
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
