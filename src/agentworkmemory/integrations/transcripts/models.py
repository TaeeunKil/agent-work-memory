from datetime import datetime
from pathlib import Path
from typing import Protocol

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.sessions.models import AgentEvent, AgentProviderId


class DiscoveredAgentSession(AgentWorkMemoryModel):
    provider: AgentProviderId
    provider_session_id: str
    title: str | None = None
    cwd: Path | None
    source_path: Path
    content_path: Path | None = None
    modified_at: datetime
    size_bytes: int
    started_at: datetime | None = None


class TranscriptReadResult(AgentWorkMemoryModel):
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
