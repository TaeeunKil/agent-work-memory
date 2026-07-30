from datetime import datetime
from pathlib import Path

from workalmanac.services.auto_distillation.models import AutoDistillSettings


class UnsupportedAutoDistillSchedulerAdapter:
    task_name = "WorkAlmanac Auto Distill"

    def available(self) -> bool:
        return False

    def install(self, settings: AutoDistillSettings, state_dir: Path) -> None:
        raise RuntimeError("automatic distillation is unavailable")

    def installed(self) -> bool:
        return False

    def next_run_at(self) -> datetime | None:
        return None

    def remove(self) -> None:
        return None
