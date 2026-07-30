from datetime import UTC, datetime

from filelock import FileLock

from agentworkmemory.services.remotes.errors import RemoteAccessError
from agentworkmemory.services.remotes.models import (
    RemoteHost,
    RemoteOverview,
    RemoteSnapshot,
    RemoteSyncState,
    RemoteSyncStatus,
    validate_remote_target,
)
from agentworkmemory.services.remotes.ports import RemoteSnapshotAdapter
from agentworkmemory.services.remotes.store import RemoteStore
from agentworkmemory.services.sessions.models import (
    AgentProvider,
    AgentProviderId,
)


class RemotesService:
    def __init__(
        self,
        store: RemoteStore,
        adapter: RemoteSnapshotAdapter,
    ):
        self.store = store
        self.adapter = adapter

    def register(
        self,
        target: str,
        providers: tuple[AgentProviderId, ...] = (
            AgentProvider.CODEX,
            AgentProvider.CLAUDE,
        ),
    ) -> RemoteHost:
        target = validate_remote_target(target)
        existing = self.store.get_host(target)
        host = RemoteHost(
            target=target,
            providers=providers,
            added_at=existing.added_at if existing is not None else datetime.now(UTC),
        )
        self.store.save_host(host)
        return host

    def remove(self, target: str) -> bool:
        return self.store.remove_host(target)

    def get(self, target: str) -> RemoteHost:
        host = self.store.get_host(target)
        if host is None:
            raise KeyError(f"unknown remote host: {target}")
        return host

    def list(self) -> tuple[RemoteOverview, ...]:
        return tuple(self.overview(host) for host in self.store.list_hosts())

    def overview(self, host: RemoteHost) -> RemoteOverview:
        status = self.store.status(host.target) or RemoteSyncStatus(
            target=host.target
        )
        return RemoteOverview(host=host, status=status)

    def snapshot(self, host: RemoteHost) -> RemoteSnapshot:
        host_root = self.store.host_root(host.target)
        host_root.mkdir(parents=True, exist_ok=True)
        with FileLock(host_root / "snapshot.lock"):
            return self.locked_snapshot(host)

    def locked_snapshot(self, host: RemoteHost) -> RemoteSnapshot:
        attempted_at = datetime.now(UTC)
        previous = self.store.manifest(host.target)
        try:
            snapshot = self.adapter.snapshot(
                host,
                previous,
                self.store.cache_root(host.target),
            )
        except RemoteAccessError as error:
            prior = self.store.status(host.target)
            self.store.save_status(
                RemoteSyncStatus(
                    target=host.target,
                    state=RemoteSyncState.FAILED,
                    last_attempt_at=attempted_at,
                    last_success_at=(
                        prior.last_success_at if prior is not None else None
                    ),
                    files_observed=(
                        prior.files_observed if prior is not None else 0
                    ),
                    files_downloaded=(
                        prior.files_downloaded if prior is not None else 0
                    ),
                    bytes_downloaded=(
                        prior.bytes_downloaded if prior is not None else 0
                    ),
                    error_type=error.kind.value,
                )
            )
            raise
        self.store.save_manifest(host.target, snapshot.manifest)
        self.store.save_status(
            RemoteSyncStatus(
                target=host.target,
                state=RemoteSyncState.SUCCEEDED,
                last_attempt_at=attempted_at,
                last_success_at=datetime.now(UTC),
                files_observed=len(snapshot.manifest.files),
                files_downloaded=snapshot.files_downloaded,
                bytes_downloaded=snapshot.bytes_downloaded,
            )
        )
        return snapshot
