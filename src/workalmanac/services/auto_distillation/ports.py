from datetime import datetime
from pathlib import Path
from typing import Protocol

from workalmanac.services.auto_distillation.models import AutoDistillSettings


class AutoDistillSchedulerAdapter(Protocol):
    task_name: str

    def available(self) -> bool: ...

    def install(self, settings: AutoDistillSettings, state_dir: Path) -> None: ...

    def installed(self) -> bool: ...

    def next_run_at(self) -> datetime | None: ...

    def remove(self) -> None: ...
