from pathlib import Path

from agentworkmemory.services.vault.service import VaultService
from agentworkmemory.services.vault_repository.models import (
    VaultRepositoryResult,
    VaultRepositoryStatus,
)
from agentworkmemory.services.vault_repository.ports import VaultRepositoryAdapter

DEFAULT_COMMIT_MESSAGE = "Update Agent Work Memory Vault"
VAULT_GITIGNORE = """# Local editor state
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.trash/

# Operating-system metadata
.DS_Store
Thumbs.db
"""


class VaultRepositoryService:
    def __init__(
        self,
        vault: VaultService,
        adapter: VaultRepositoryAdapter,
    ):
        self.vault = vault
        self.adapter = adapter

    def connect(self, repository: str, destination: Path) -> Path:
        target = destination.expanduser().resolve()
        self.adapter.clone(repository, target)
        return self.vault.initialize(target)

    def publish(self, repository: str) -> VaultRepositoryResult:
        root = self.vault.require_path()
        ensure_gitignore(root)
        self.adapter.initialize(root, repository)
        committed = self.adapter.commit_all(root, "Initialize Agent Work Memory Vault")
        self.adapter.push(root)
        return VaultRepositoryResult(path=root, committed=committed)

    def status(self) -> VaultRepositoryStatus:
        return self.adapter.status(self.vault.require_path())

    def pull(self) -> VaultRepositoryResult:
        root = self.vault.require_path()
        status = self.adapter.status(root)
        if not status.clean:
            raise RuntimeError(
                "Vault has local changes; run `awm vault sync` or "
                "`awm vault push` before pulling"
            )
        self.adapter.pull_rebase(root)
        return VaultRepositoryResult(path=root)

    def push(self, message: str = DEFAULT_COMMIT_MESSAGE) -> VaultRepositoryResult:
        root = self.vault.require_path()
        ensure_gitignore(root)
        committed = self.adapter.commit_all(root, message)
        self.adapter.push(root)
        return VaultRepositoryResult(path=root, committed=committed)

    def sync(self, message: str = DEFAULT_COMMIT_MESSAGE) -> VaultRepositoryResult:
        root = self.vault.require_path()
        ensure_gitignore(root)
        committed = self.adapter.commit_all(root, message)
        self.adapter.pull_rebase(root)
        self.adapter.push(root)
        return VaultRepositoryResult(path=root, committed=committed)


def ensure_gitignore(root: Path) -> None:
    target = root / ".gitignore"
    if target.exists():
        return
    target.write_text(VAULT_GITIGNORE, encoding="utf-8")

