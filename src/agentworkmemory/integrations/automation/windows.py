import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from agentworkmemory.integrations.processes import hidden_process_creation_flags
from agentworkmemory.services.automation.models import AutoSyncSettings

TASK_NAME = "AWM Sync"


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

    def next_run_at(self) -> datetime | None:
        return scheduled_task_next_run(self.task_name)

    def remove(self) -> None:
        completed = run_schtasks(("/Delete", "/F", "/TN", self.task_name))
        if completed.returncode != 0:
            raise RuntimeError("Windows Task Scheduler could not remove collection")


def scheduled_sync_action(settings: AutoSyncSettings, state_dir: Path) -> str:
    command = [
        background_python_executable(),
        "-m",
        "agentworkmemory.scheduled",
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


def background_python_executable() -> str:
    return str(Path(sys.executable).with_name("pythonw.exe"))


def run_schtasks(arguments: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("schtasks.exe", *arguments),
        capture_output=True,
        text=True,
        check=False,
        creationflags=hidden_process_creation_flags(),
    )


def scheduled_task_next_run(task_name: str) -> datetime | None:
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        return None
    escaped_name = task_name.replace("'", "''")
    command = (
        "$ErrorActionPreference='Stop';"
        "try{"
        f"$next=(Get-ScheduledTaskInfo -TaskName '{escaped_name}').NextRunTime"
        "}catch{"
        f"$csv=& schtasks.exe /Query /TN '{escaped_name}' /FO CSV /V;"
        "if($LASTEXITCODE -ne 0){exit 1};"
        "$row=@($csv|ConvertFrom-Csv)[0];"
        "$next=[datetime]::Parse($row.PSObject.Properties[2].Value)"
        "};"
        "$value=$next.ToUniversalTime().ToString('o');"
        "[pscustomobject]@{next_run_at=$value}|ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            (powershell, "-NoProfile", "-NonInteractive", "-Command", command),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=10,
            creationflags=hidden_process_creation_flags(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout)
        value = payload["next_run_at"]
        parsed = datetime.fromisoformat(value)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return parsed if parsed.tzinfo is not None else None
