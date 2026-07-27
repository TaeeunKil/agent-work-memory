from pathlib import Path

from filelock import FileLock, Timeout

from workalmanac.services.search import SearchService
from workalmanac.services.synchronization import (
    SynchronizationService,
    SyncReceipt,
    SyncStatus,
)
from workalmanac.workflows.collect import (
    CollectAgentRecords,
    CollectAgentRecordsWorkflow,
)
from workalmanac.workflows.sync.models import SyncAgentRecords


class SyncAgentRecordsWorkflow:
    def __init__(
        self,
        collect: CollectAgentRecordsWorkflow,
        search: SearchService,
        synchronization: SynchronizationService,
        lock_path: Path,
    ):
        self.collect = collect
        self.search = search
        self.synchronization = synchronization
        self.lock_path = lock_path

    def run(self, request: SyncAgentRecords) -> SyncReceipt:
        receipt = self.synchronization.begin(
            providers=request.providers,
            include_content=request.include_content,
        )
        lock = FileLock(self.lock_path, timeout=0)
        try:
            with lock:
                collection = self.collect.collect(
                    CollectAgentRecords(
                        providers=request.providers,
                        home=request.home,
                        include_content=request.include_content,
                    )
                )
                self.search.refresh()
        except Timeout:
            return self.synchronization.finish(
                receipt,
                status=SyncStatus.SKIPPED_LOCKED,
            )
        except Exception as error:
            self.synchronization.finish(
                receipt,
                status=SyncStatus.FAILED,
                error_type=type(error).__name__,
            )
            raise RuntimeError(
                "Work Almanac sync failed; inspect sync status"
            ) from error
        return self.synchronization.finish(
            receipt,
            status=SyncStatus.SUCCEEDED,
            collection=collection,
        )
