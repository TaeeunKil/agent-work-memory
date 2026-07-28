from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.sessions.models import AgentProviderId
from agentworkmemory.workflows.collect.models import CollectionReceipt


class SyncRemoteRecords(AgentWorkMemoryModel):
    targets: tuple[str, ...] = ()
    providers: tuple[AgentProviderId, ...] | None = None
    include_content: bool = False


class RemoteCollectionResult(AgentWorkMemoryModel):
    target: str
    succeeded: bool
    files_downloaded: int = 0
    bytes_downloaded: int = 0
    sessions_discovered: int = 0
    events_added: int = 0
    error_type: str | None = None


class RemoteCollectionReceipt(AgentWorkMemoryModel):
    collection: CollectionReceipt
    remotes: tuple[RemoteCollectionResult, ...]
