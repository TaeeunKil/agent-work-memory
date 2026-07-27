from pathlib import Path

from workalmanac.core import WorkAlmanacModel


class ImportLegacyAlmanac(WorkAlmanacModel):
    source: Path


class LegacyImportReceipt(WorkAlmanacModel):
    namespace: str
    files_discovered: int
    files_copied: int
    files_unchanged: int
    target: Path
