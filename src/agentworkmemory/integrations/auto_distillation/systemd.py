import shutil
import sys
from datetime import datetime
from pathlib import Path

from agentworkmemory.integrations.automation.systemd import (
    reload_user_systemd,
    render_interval_timer,
    render_oneshot_service,
    run_systemctl,
    surface_process_error,
    timer_next_run_at,
    user_unit_dir,
)
from agentworkmemory.services.auto_distillation.models import AutoDistillSettings

SERVICE_UNIT = "awm-auto-distill.service"
TIMER_UNIT = "awm-auto-distill.timer"
TASK_NAME = TIMER_UNIT


class SystemdAutoDistillSchedulerAdapter:
    """Install automatic distillation with a systemd --user timer on Linux."""

    task_name = TASK_NAME
    service_unit = SERVICE_UNIT
    timer_unit = TIMER_UNIT

    def available(self) -> bool:
        return sys.platform.startswith("linux") and shutil.which("systemctl") is not None

    def install(self, settings: AutoDistillSettings, state_dir: Path) -> None:
        units = user_unit_dir()
        units.mkdir(parents=True, exist_ok=True)
        command = scheduled_auto_distill_command(state_dir)
        (units / self.service_unit).write_text(
            render_oneshot_service(
                description="Agent Work Memory automatic distillation",
                command=command,
            ),
            encoding="utf-8",
        )
        (units / self.timer_unit).write_text(
            render_interval_timer(
                description="Agent Work Memory automatic distillation timer",
                service_unit=self.service_unit,
                interval_minutes=settings.interval_minutes,
            ),
            encoding="utf-8",
        )
        reload_user_systemd()
        completed = run_systemctl(("enable", "--now", "--", self.timer_unit))
        if completed.returncode != 0:
            raise RuntimeError(
                "systemd user timer rejected automatic distillation: "
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
            raise RuntimeError(
                "systemd user units could not remove automatic distillation"
            )


def scheduled_auto_distill_command(state_dir: Path) -> tuple[str, ...]:
    return (
        sys.executable,
        "-m",
        "agentworkmemory.scheduled",
        "--state-dir",
        str(state_dir),
        "auto-distill",
        "run",
    )
