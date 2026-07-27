from datetime import datetime
from pathlib import Path
from typing import Protocol

from workalmanac.core import WorkAlmanacModel
from workalmanac.services.sessions.models import AgentEvent, AgentProviderId


class DiscoveredAgentSession(WorkAlmanacModel):
    provider: AgentProviderId
    provider_session_id: str
    cwd: Path | None
    source_path: Path
    modified_at: datetime
    size_bytes: int
    started_at: datetime | None = None


class TranscriptReadResult(WorkAlmanacModel):
    events: tuple[AgentEvent, ...]
    last_line: int
    size_bytes: int


class TranscriptCollector(Protocol):
    provider: AgentProviderId

    def discover(self, home: Path) -> tuple[DiscoveredAgentSession, ...]: ...

    def read(
        self,
        session: DiscoveredAgentSession,
        *,
        work_session_id: str,
        after_line: int,
    ) -> TranscriptReadResult: ...
