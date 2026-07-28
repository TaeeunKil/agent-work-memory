from datetime import UTC, datetime
from uuid import uuid4

from agentworkmemory.services.sessions.models import AgentProviderId
from agentworkmemory.services.synchronization.models import SyncReceipt, SyncStatus
from agentworkmemory.services.synchronization.store import SynchronizationStore
from agentworkmemory.workflows.collect.models import CollectionReceipt


class SynchronizationService:
    def __init__(self, store: SynchronizationStore):
        self.store = store

    def begin(
        self,
        *,
        providers: tuple[AgentProviderId, ...],
        include_content: bool,
    ) -> SyncReceipt:
        return self.store.remember(
            SyncReceipt(
                run_id=f"syn_{uuid4().hex}",
                providers=providers,
                include_content=include_content,
                status=SyncStatus.RUNNING,
                started_at=datetime.now(UTC),
            )
        )

    def finish(
        self,
        receipt: SyncReceipt,
        *,
        status: SyncStatus,
        collection: CollectionReceipt | None = None,
        error_type: str | None = None,
    ) -> SyncReceipt:
        update: dict[str, object] = {
            "status": status,
            "error_type": error_type,
            "finished_at": datetime.now(UTC),
        }
        if collection is not None:
            update.update(
                {
                    "sessions_discovered": collection.sessions_discovered,
                    "sessions_updated": collection.sessions_updated,
                    "events_added": collection.events_added,
                }
            )
        return self.store.remember(receipt.model_copy(update=update))

    def skipped_locked(
        self,
        *,
        providers: tuple[AgentProviderId, ...],
        include_content: bool,
    ) -> SyncReceipt:
        now = datetime.now(UTC)
        return SyncReceipt(
            run_id=f"syn_{uuid4().hex}",
            providers=providers,
            include_content=include_content,
            status=SyncStatus.SKIPPED_LOCKED,
            started_at=now,
            finished_at=now,
        )

    def latest(self) -> SyncReceipt | None:
        return self.store.latest()

    def list(self, limit: int = 50) -> tuple[SyncReceipt, ...]:
        return self.store.list(limit)
