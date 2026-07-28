from workalmanac.core import WorkAlmanacModel
from workalmanac.services.sessions.models import AgentProviderId
from workalmanac.workflows.collect.models import CollectionReceipt


class SyncRemoteRecords(WorkAlmanacModel):
    targets: tuple[str, ...] = ()
    providers: tuple[AgentProviderId, ...] | None = None
    include_content: bool = False


class RemoteCollectionResult(WorkAlmanacModel):
    target: str
    succeeded: bool
    files_downloaded: int = 0
    bytes_downloaded: int = 0
    sessions_discovered: int = 0
    events_added: int = 0
    error_type: str | None = None


class RemoteCollectionReceipt(WorkAlmanacModel):
    collection: CollectionReceipt
    remotes: tuple[RemoteCollectionResult, ...]
