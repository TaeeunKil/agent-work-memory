import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from agentworkmemory.services.automation.models import AutoSyncSettings

SERVICE_UNIT = "awm-sync.service"
TIMER_UNIT = "awm-sync.timer"
TASK_NAME = TIMER_UNIT


class SystemdSchedulerAdapter:
    """Install automatic collection with a systemd --user timer on Linux."""

    task_name = TASK_NAME
    service_unit = SERVICE_UNIT
    timer_unit = TIMER_UNIT

    def available(self) -> bool:
        return sys.platform.startswith("linux") and shutil.which("systemctl") is not None

    def install(self, settings: AutoSyncSettings, state_dir: Path) -> None:
        units = user_unit_dir()
        units.mkdir(parents=True, exist_ok=True)
        command = scheduled_sync_command(settings, state_dir)
        (units / self.service_unit).write_text(
            render_oneshot_service(
                description="Agent Work Memory automatic sync",
                command=command,
            ),
            encoding="utf-8",
        )
        (units / self.timer_unit).write_text(
            render_interval_timer(
                description="Agent Work Memory automatic sync timer",
                service_unit=self.service_unit,
                interval_minutes=settings.interval_minutes,
            ),
            encoding="utf-8",
        )
        reload_user_systemd()
        completed = run_systemctl(
            ("enable", "--now", "--", self.timer_unit),
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "systemd user timer rejected automatic collection: "
                f"{surface_process_error(completed)}"
            )

    def installed(self) -> bool:
        if not (user_unit_dir() / self.timer_unit).is_file():
            return False
        completed = run_systemctl(("is-enabled", "--", self.timer_unit))
        return completed.returncode == 0 and completed.stdout.strip() in {
            "enabled",
            "enabled-runtime",
            "static",
        }

    def next_run_at(self) -> datetime | None:
        return timer_next_run_at(self.timer_unit)

    def remove(self) -> None:
        units = user_unit_dir()
        run_systemctl(("disable", "--now", "--", self.timer_unit))
        run_systemctl(("stop", "--", self.service_unit))
        (units / self.timer_unit).unlink(missing_ok=True)
        (units / self.service_unit).unlink(missing_ok=True)
        reload_user_systemd()
        if (units / self.timer_unit).exists() or (units / self.service_unit).exists():
            raise RuntimeError("systemd user units could not remove collection")


def scheduled_sync_command(settings: AutoSyncSettings, state_dir: Path) -> tuple[str, ...]:
    command = [
        sys.executable,
        "-m",
        "agentworkmemory.scheduled",
        "--state-dir",
        str(state_dir),
        "sync",
        "--home",
        str(settings.home),
    ]
    for provider in settings.providers:
        command.extend(("--from", str(provider)))
    if settings.include_content:
        command.append("--include-content")
    return tuple(command)


def user_unit_dir() -> Path:
    config_home = Path(
        __import__("os").environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    ).expanduser()
    return config_home / "systemd" / "user"


def render_oneshot_service(*, description: str, command: tuple[str, ...]) -> str:
    exec_start = " ".join(systemd_quote(part) for part in command)
    return (
        "[Unit]\n"
        f"Description={description}\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={exec_start}\n"
    )


def render_interval_timer(
    *,
    description: str,
    service_unit: str,
    interval_minutes: int,
) -> str:
    return (
        "[Unit]\n"
        f"Description={description}\n"
        "\n"
        "[Timer]\n"
        "OnBootSec=1min\n"
        f"OnUnitActiveSec={interval_minutes}min\n"
        "Persistent=true\n"
        f"Unit={service_unit}\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def systemd_quote(value: str) -> str:
    if value == "" or any(character.isspace() for character in value) or any(
        character in value for character in '"\\'
    ):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def reload_user_systemd() -> None:
    run_systemctl(("daemon-reload",))


def run_systemctl(arguments: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        return subprocess.CompletedProcess(
            args=("systemctl", *arguments),
            returncode=1,
            stdout="",
            stderr="systemctl not found",
        )
    return subprocess.run(
        (systemctl, "--user", *arguments),
        capture_output=True,
        text=True,
        check=False,
    )


def timer_next_run_at(timer_unit: str) -> datetime | None:
    completed = run_systemctl(
        ("show", timer_unit, "--property=NextElapseUSecRealtime", "--value"),
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    if not value or value in {"infinity", "n/a", "0"}:
        return None
    try:
        microseconds = int(value)
    except ValueError:
        return None
    if microseconds <= 0:
        return None
    return datetime.fromtimestamp(microseconds / 1_000_000, UTC)


def surface_process_error(completed: subprocess.CompletedProcess[str]) -> str:
    detail = (completed.stderr or completed.stdout or "").strip()
    return detail or f"exit {completed.returncode}"
