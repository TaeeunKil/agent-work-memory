from hashlib import sha256
from pathlib import Path

from filelock import FileLock

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.remotes.models import (
    RemoteHost,
    RemoteManifest,
    RemoteRegistry,
    RemoteStatusLedger,
    RemoteSyncStatus,
)


class RemoteStore:
    def __init__(self, root: Path):
        self.root = root
        self.registry_path = root / "registry.json"
        self.status_path = root / "status.json"
        self.lock_path = root / "registry.lock"

    def list_hosts(self) -> tuple[RemoteHost, ...]:
        return self.registry().hosts

    def get_host(self, target: str) -> RemoteHost | None:
        identity = target.casefold()
        return next(
            (
                host
                for host in self.registry().hosts
                if host.target.casefold() == identity
            ),
            None,
        )

    def save_host(self, host: RemoteHost) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with FileLock(self.lock_path):
            hosts = [
                current
                for current in self.registry().hosts
                if current.target.casefold() != host.target.casefold()
            ]
            hosts.append(host)
            self.write_model(
                self.registry_path,
                RemoteRegistry(hosts=tuple(sorted(hosts, key=host_sort_key))),
            )

    def remove_host(self, target: str) -> bool:
        self.root.mkdir(parents=True, exist_ok=True)
        with FileLock(self.lock_path):
            registry = self.registry()
            hosts = tuple(
                host
                for host in registry.hosts
                if host.target.casefold() != target.casefold()
            )
            if len(hosts) == len(registry.hosts):
                return False
            self.write_model(self.registry_path, RemoteRegistry(hosts=hosts))
            return True

    def status(self, target: str) -> RemoteSyncStatus | None:
        identity = target.casefold()
        return next(
            (
                status
                for status in self.status_ledger().statuses
                if status.target.casefold() == identity
            ),
            None,
        )

    def save_status(self, status: RemoteSyncStatus) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with FileLock(self.lock_path):
            statuses = [
                current
                for current in self.status_ledger().statuses
                if current.target.casefold() != status.target.casefold()
            ]
            statuses.append(status)
            self.write_model(
                self.status_path,
                RemoteStatusLedger(
                    statuses=tuple(sorted(statuses, key=status_sort_key))
                ),
            )

    def manifest(self, target: str) -> RemoteManifest:
        path = self.host_root(target) / "manifest.json"
        if not path.is_file():
            return RemoteManifest()
        return RemoteManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def save_manifest(self, target: str, manifest: RemoteManifest) -> None:
        self.write_model(self.host_root(target) / "manifest.json", manifest)

    def cache_root(self, target: str) -> Path:
        return self.host_root(target) / "snapshot"

    def registry(self) -> RemoteRegistry:
        if not self.registry_path.is_file():
            return RemoteRegistry()
        return RemoteRegistry.model_validate_json(
            self.registry_path.read_text(encoding="utf-8")
        )

    def status_ledger(self) -> RemoteStatusLedger:
        if not self.status_path.is_file():
            return RemoteStatusLedger()
        return RemoteStatusLedger.model_validate_json(
            self.status_path.read_text(encoding="utf-8")
        )

    def host_root(self, target: str) -> Path:
        identity = sha256(target.casefold().encode()).hexdigest()[:20]
        return self.root / identity

    def write_model(self, path: Path, model: AgentWorkMemoryModel) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        temporary.write_text(
            model.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)


def host_sort_key(host: RemoteHost) -> str:
    return host.target.casefold()


def status_sort_key(status: RemoteSyncStatus) -> str:
    return status.target.casefold()
