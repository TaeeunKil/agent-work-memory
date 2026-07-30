from pathlib import Path
from typing import Protocol

from workalmanac.services.automation.models import AutoSyncSettings


class SchedulerAdapter(Protocol):
    task_name: str

    def available(self) -> bool: ...

    def install(self, settings: AutoSyncSettings, state_dir: Path) -> None: ...

    def installed(self) -> bool: ...

    def remove(self) -> None: ...
