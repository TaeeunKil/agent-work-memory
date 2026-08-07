from datetime import UTC, datetime
from pathlib import Path

from agentworkmemory.integrations.auto_distillation import (
    default_auto_distill_scheduler_adapter,
)
from agentworkmemory.integrations.auto_distillation.systemd import (
    SystemdAutoDistillSchedulerAdapter,
    scheduled_auto_distill_command,
)
from agentworkmemory.integrations.automation import default_scheduler_adapter
from agentworkmemory.integrations.automation.systemd import (
    SystemdSchedulerAdapter,
    render_interval_timer,
    render_oneshot_service,
    scheduled_sync_command,
    systemd_quote,
    timer_next_run_at,
)
from agentworkmemory.services.automation.models import AutoSyncSettings
from agentworkmemory.services.sessions.models import AgentProvider


def test_default_scheduler_adapter_selects_systemd_on_linux(
    monkeypatch,
):
    monkeypatch.setattr("agentworkmemory.integrations.automation.os.name", "posix")
    monkeypatch.setattr(
        "agentworkmemory.integrations.automation.sys.platform",
        "linux",
    )
    assert isinstance(default_scheduler_adapter(), SystemdSchedulerAdapter)


def test_default_auto_distill_adapter_selects_systemd_on_linux(monkeypatch):
    monkeypatch.setattr(
        "agentworkmemory.integrations.auto_distillation.os.name",
        "posix",
    )
    monkeypatch.setattr(
        "agentworkmemory.integrations.auto_distillation.sys.platform",
        "linux",
    )
    assert isinstance(
        default_auto_distill_scheduler_adapter(),
        SystemdAutoDistillSchedulerAdapter,
    )


def test_scheduled_sync_command_includes_providers_and_content(tmp_path: Path):
    settings = AutoSyncSettings(
        interval_minutes=5,
        providers=(AgentProvider.CODEX, AgentProvider.CURSOR),
        home=tmp_path / "User Home",
        include_content=True,
    )

    command = scheduled_sync_command(settings, tmp_path / "State Dir")

    assert "-m" in command
    assert "agentworkmemory.scheduled" in command
    assert command.count("--from") == 2
    assert "codex" in command
    assert "cursor" in command
    assert "--include-content" in command
    assert "distill" not in command


def test_scheduled_auto_distill_command_targets_run(tmp_path: Path):
    command = scheduled_auto_distill_command(tmp_path / "state")
    assert command[-2:] == ("auto-distill", "run")
    assert "--state-dir" in command


def test_render_systemd_units_quote_paths_and_interval():
    service = render_oneshot_service(
        description="Agent Work Memory automatic sync",
        command=(
            "/usr/bin/python3",
            "-m",
            "agentworkmemory.scheduled",
            "--state-dir",
            "/home/user/State Dir",
            "sync",
            "--home",
            "/home/user",
            "--from",
            "cursor",
        ),
    )
    timer = render_interval_timer(
        description="Agent Work Memory automatic sync timer",
        service_unit="awm-sync.service",
        interval_minutes=7,
    )

    assert 'ExecStart=/usr/bin/python3 -m agentworkmemory.scheduled --state-dir "/home/user/State Dir" sync --home /home/user --from cursor' in service
    assert "OnUnitActiveSec=7min" in timer
    assert "Unit=awm-sync.service" in timer
    assert "WantedBy=timers.target" in timer


def test_systemd_quote_escapes_spaces_and_quotes():
    assert systemd_quote("plain") == "plain"
    assert systemd_quote("a b") == '"a b"'
    assert systemd_quote('say "hi"') == '"say \\"hi\\""'


def test_timer_next_run_at_parses_usec(monkeypatch):
    class Completed:
        returncode = 0
        stdout = "1754542800000000\n"
        stderr = ""

    monkeypatch.setattr(
        "agentworkmemory.integrations.automation.systemd.run_systemctl",
        lambda arguments: Completed(),
    )
    value = timer_next_run_at("awm-sync.timer")
    assert value == datetime.fromtimestamp(1754542800, UTC)
