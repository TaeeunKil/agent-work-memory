from pathlib import Path

from agentworkmemory.core import AgentWorkMemoryModel


class ImportLegacyAlmanac(AgentWorkMemoryModel):
    source: Path


class ValidatedLegacyPage(AgentWorkMemoryModel):
    relative_path: Path
    content: bytes


class LegacyImportReceipt(AgentWorkMemoryModel):
    namespace: str
    files_discovered: int
    files_copied: int
    files_unchanged: int
    target: Path
