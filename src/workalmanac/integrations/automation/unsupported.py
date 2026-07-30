from datetime import datetime
from pathlib import Path

from workalmanac.services.automation.models import AutoSyncSettings


class UnsupportedSchedulerAdapter:
    task_name = "WorkAlmanac Sync"

    def available(self) -> bool:
        return False

    def install(self, settings: AutoSyncSettings, state_dir: Path) -> None:
        raise RuntimeError("automatic collection is unavailable on this platform")

    def installed(self) -> bool:
        return False

    def next_run_at(self) -> datetime | None:
        return None

    def remove(self) -> None:
        return None
