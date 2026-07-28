import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from workalmanac.integrations.automation.windows import (
    background_python_executable,
    run_schtasks,
    scheduled_task_next_run,
)
from workalmanac.services.auto_distillation.models import AutoDistillSettings

TASK_NAME = "WorkAlmanac Auto Distill"


class WindowsAutoDistillSchedulerAdapter:
    task_name = TASK_NAME

    def available(self) -> bool:
        return shutil.which("schtasks.exe") is not None

    def install(self, settings: AutoDistillSettings, state_dir: Path) -> None:
        completed = run_schtasks(
            (
                "/Create",
                "/F",
                "/SC",
                "MINUTE",
                "/MO",
                str(settings.interval_minutes),
                "/TN",
                self.task_name,
                "/TR",
                scheduled_auto_distill_action(state_dir),
            )
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "Windows Task Scheduler rejected automatic distillation"
            )

    def installed(self) -> bool:
        completed = run_schtasks(("/Query", "/TN", self.task_name))
        return completed.returncode == 0

    def next_run_at(self) -> datetime | None:
        return scheduled_task_next_run(self.task_name)

    def remove(self) -> None:
        completed = run_schtasks(("/Delete", "/F", "/TN", self.task_name))
        if completed.returncode != 0:
            raise RuntimeError(
                "Windows Task Scheduler could not remove automatic distillation"
            )


def scheduled_auto_distill_action(state_dir: Path) -> str:
    return subprocess.list2cmdline(
        (
            background_python_executable(),
            "-m",
            "workalmanac.scheduled",
            "--state-dir",
            str(state_dir),
            "auto-distill",
            "run",
        )
    )
