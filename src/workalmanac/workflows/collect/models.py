from pathlib import Path

from workalmanac.core import WorkAlmanacModel
from workalmanac.services.sessions.models import AgentProviderId


class CollectAgentRecords(WorkAlmanacModel):
    providers: tuple[AgentProviderId, ...]
    home: Path
    include_content: bool = False


class CollectionReceipt(WorkAlmanacModel):
    sessions_discovered: int
    sessions_updated: int
    events_added: int
    session_ids: tuple[str, ...]
