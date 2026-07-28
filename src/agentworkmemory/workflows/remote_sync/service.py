from agentworkmemory.services.remotes.errors import RemoteAccessError
from agentworkmemory.services.remotes.service import RemotesService
from agentworkmemory.workflows.collect import (
    CollectAgentRecords,
    CollectAgentRecordsWorkflow,
    CollectionReceipt,
    combine_collection_receipts,
)
from agentworkmemory.workflows.remote_sync.models import (
    RemoteCollectionReceipt,
    RemoteCollectionResult,
    SyncRemoteRecords,
)


class SyncRemoteRecordsWorkflow:
    def __init__(
        self,
        remotes: RemotesService,
        collect: CollectAgentRecordsWorkflow,
    ):
        self.remotes = remotes
        self.collect = collect

    def run(self, request: SyncRemoteRecords) -> RemoteCollectionReceipt:
        hosts = (
            tuple(self.remotes.get(target) for target in request.targets)
            if request.targets
            else tuple(overview.host for overview in self.remotes.list())
        )
        receipts: list[CollectionReceipt] = []
        results: list[RemoteCollectionResult] = []
        for host in hosts:
            selected = tuple(
                provider
                for provider in host.providers
                if request.providers is None or provider in request.providers
            )
            if not selected:
                continue
            try:
                snapshot = self.remotes.snapshot(host)
            except RemoteAccessError as error:
                results.append(
                    RemoteCollectionResult(
                        target=host.target,
                        succeeded=False,
                        error_type=error.kind.value,
                    )
                )
                continue
            collection = self.collect.collect(
                CollectAgentRecords(
                    providers=selected,
                    home=snapshot.local_home,
                    include_content=request.include_content,
                )
            )
            receipts.append(collection)
            results.append(
                RemoteCollectionResult(
                    target=host.target,
                    succeeded=True,
                    files_downloaded=snapshot.files_downloaded,
                    bytes_downloaded=snapshot.bytes_downloaded,
                    sessions_discovered=collection.sessions_discovered,
                    events_added=collection.events_added,
                )
            )
        return RemoteCollectionReceipt(
            collection=combine_collection_receipts(tuple(receipts)),
            remotes=tuple(results),
        )
