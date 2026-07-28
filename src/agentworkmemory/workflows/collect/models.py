from pathlib import Path

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.sessions.models import AgentProviderId


class CollectAgentRecords(AgentWorkMemoryModel):
    providers: tuple[AgentProviderId, ...]
    home: Path
    include_content: bool = False


class CollectionReceipt(AgentWorkMemoryModel):
    sessions_discovered: int
    sessions_updated: int
    events_added: int
    session_ids: tuple[str, ...]
