from pathlib import Path

from agentworkmemory.core import AgentWorkMemoryModel


class VaultRepositoryStatus(AgentWorkMemoryModel):
    path: Path
    branch: str
    remote: str
    clean: bool
    changes: int


class VaultRepositoryResult(AgentWorkMemoryModel):
    path: Path
    committed: bool = False

