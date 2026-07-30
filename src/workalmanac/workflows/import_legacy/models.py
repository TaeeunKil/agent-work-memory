from pathlib import Path

from workalmanac.core import WorkAlmanacModel


class ImportLegacyAlmanac(WorkAlmanacModel):
    source: Path


class ValidatedLegacyPage(WorkAlmanacModel):
    relative_path: Path
    content: bytes


class LegacyImportReceipt(WorkAlmanacModel):
    namespace: str
    files_discovered: int
    files_copied: int
    files_unchanged: int
    target: Path
