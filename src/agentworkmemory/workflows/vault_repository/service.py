from pathlib import Path

from agentworkmemory.services.search.service import SearchService
from agentworkmemory.services.vault_repository.models import (
    VaultRepositoryResult,
    VaultRepositoryStatus,
)
from agentworkmemory.services.vault_repository.service import VaultRepositoryService
from agentworkmemory.services.wiki.service import WikiCatalogService


class VaultRepositoryWorkflow:
    def __init__(
        self,
        repository: VaultRepositoryService,
        wiki: WikiCatalogService,
        search: SearchService,
    ):
        self.repository = repository
        self.wiki = wiki
        self.search = search

    def connect(self, repository: str, destination: Path) -> Path:
        path = self.repository.connect(repository, destination)
        self.refresh_local_views()
        return path

    def publish(self, repository: str) -> VaultRepositoryResult:
        self.refresh_local_views()
        return self.repository.publish(repository)

    def status(self) -> VaultRepositoryStatus:
        return self.repository.status()

    def pull(self) -> VaultRepositoryResult:
        result = self.repository.pull()
        self.refresh_local_views()
        return result

    def push(self, message: str) -> VaultRepositoryResult:
        self.refresh_local_views()
        return self.repository.push(message)

    def sync(self, message: str) -> VaultRepositoryResult:
        self.refresh_local_views()
        result = self.repository.sync(message)
        self.refresh_local_views()
        follow_up = self.repository.push(message)
        if follow_up.committed:
            result = follow_up
        return result

    def refresh_local_views(self) -> None:
        self.wiki.refresh()
        self.search.refresh()
