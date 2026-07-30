import shutil
import subprocess
import sys
from pathlib import Path

from workalmanac.services.automation.models import AutoSyncSettings

TASK_NAME = "WorkAlmanac Sync"


class WindowsSchedulerAdapter:
    task_name = TASK_NAME

    def available(self) -> bool:
        return shutil.which("schtasks.exe") is not None

    def install(self, settings: AutoSyncSettings, state_dir: Path) -> None:
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
                scheduled_sync_action(settings, state_dir),
            )
        )
        if completed.returncode != 0:
            raise RuntimeError("Windows Task Scheduler rejected automatic collection")

    def installed(self) -> bool:
        completed = run_schtasks(("/Query", "/TN", self.task_name))
        return completed.returncode == 0

    def remove(self) -> None:
        completed = run_schtasks(("/Delete", "/F", "/TN", self.task_name))
        if completed.returncode != 0:
            raise RuntimeError("Windows Task Scheduler could not remove collection")


def scheduled_sync_action(settings: AutoSyncSettings, state_dir: Path) -> str:
    command = [
        sys.executable,
        "-m",
        "workalmanac.cli",
        "--state-dir",
        state_dir,
        "sync",
        "--home",
        str(settings.home),
    ]
    for provider in settings.providers:
        command.extend(("--from", provider))
    if settings.include_content:
        command.append("--include-content")
    return subprocess.list2cmdline(command)


def run_schtasks(arguments: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    creationflags = 0x08000000 if sys.platform == "win32" else 0
    return subprocess.run(
        ("schtasks.exe", *arguments),
        capture_output=True,
        text=True,
        check=False,
        creationflags=creationflags,
    )
