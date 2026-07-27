import json
from pathlib import Path

import pytest
from filelock import FileLock

from workalmanac.app import create_app
from workalmanac.cli import build_parser, dispatch
from workalmanac.integrations.automation.windows import scheduled_sync_action
from workalmanac.services.automation.models import AutoSyncSettings
from workalmanac.services.sessions.models import AgentProvider
from workalmanac.services.synchronization.models import SyncStatus
from workalmanac.settings import WorkAlmanacConfig
from workalmanac.workflows.sync import SyncAgentRecords


class FakeScheduler:
    task_name = "WorkAlmanac Test Sync"

    def __init__(self):
        self.is_available = True
        self.is_installed = False
        self.installs: list[tuple[AutoSyncSettings, Path]] = []
        self.removals = 0

    def available(self) -> bool:
        return self.is_available

    def install(self, settings: AutoSyncSettings, state_dir: Path) -> None:
        self.installs.append((settings, state_dir))
        self.is_installed = True

    def installed(self) -> bool:
        return self.is_installed

    def remove(self) -> None:
        self.removals += 1
        self.is_installed = False


def test_sync_is_locked_incremental_and_searchable(tmp_path: Path):
    app = sync_app(tmp_path)
    app.vault.initialize(tmp_path / "vault")
    home = tmp_path / "home"
    write_codex_transcript(home, tmp_path / "project")
    request = SyncAgentRecords(
        providers=(AgentProvider.CODEX,),
        home=home,
        include_content=True,
    )

    first = app.sync.run(request)
    second = app.sync.run(request)

    assert first.status is SyncStatus.SUCCEEDED
    assert first.sessions_discovered == 1
    assert first.events_added == 2
    assert second.status is SyncStatus.SUCCEEDED
    assert second.events_added == 0
    assert app.synchronization.latest() == second
    assert any(result.kind == "session" for result in app.search.find("decision"))


def test_overlapping_sync_exits_without_collecting(tmp_path: Path):
    app = sync_app(tmp_path)
    app.vault.initialize(tmp_path / "vault")
    lock = FileLock(tmp_path / "state" / "sync.lock")

    with lock:
        receipt = app.sync.run(
            SyncAgentRecords(
                providers=(AgentProvider.CODEX,),
                home=tmp_path / "home",
                include_content=True,
            )
        )

    assert receipt.status is SyncStatus.SKIPPED_LOCKED
    assert app.sessions.list() == ()


def test_sync_failure_records_only_exception_type(tmp_path: Path, monkeypatch):
    app = sync_app(tmp_path)
    app.vault.initialize(tmp_path / "vault")

    def fail_refresh() -> None:
        raise ValueError("sensitive path and transcript text")

    monkeypatch.setattr(app.search, "refresh", fail_refresh)

    with pytest.raises(RuntimeError, match="inspect sync status"):
        app.sync.run(
            SyncAgentRecords(
                providers=(AgentProvider.CODEX,),
                home=tmp_path / "home",
            )
        )

    receipt = app.synchronization.latest()
    assert receipt is not None
    assert receipt.status is SyncStatus.FAILED
    assert receipt.error_type == "ValueError"
    assert "sensitive" not in receipt.model_dump_json()


def test_automation_persists_explicit_private_content_choice(tmp_path: Path):
    scheduler = FakeScheduler()
    app = sync_app(tmp_path, scheduler)
    app.vault.initialize(tmp_path / "vault")
    settings = AutoSyncSettings(
        interval_minutes=7,
        providers=(AgentProvider.CODEX,),
        home=tmp_path / "home",
        include_content=True,
    )

    status = app.automation.install(settings)

    assert status.installed
    installed, state_dir = scheduler.installs[0]
    assert installed.include_content
    assert installed.installed_at is not None
    assert state_dir == tmp_path / "state"
    assert app.automation.status().settings == installed

    app.automation.remove()

    assert scheduler.removals == 1
    assert not (tmp_path / "state" / "auto-sync.json").exists()


def test_scheduled_action_uses_module_and_no_remote_distillation(tmp_path: Path):
    settings = AutoSyncSettings(
        interval_minutes=5,
        providers=(AgentProvider.CODEX, AgentProvider.CLAUDE),
        home=tmp_path / "User Home",
        include_content=False,
    )

    action = scheduled_sync_action(settings, tmp_path / "State Dir")

    assert "-m workalmanac.cli" in action
    assert "--from codex" in action
    assert "--from claude" in action
    assert "--include-content" not in action
    assert "distill" not in action


def test_auto_install_cli_maps_explicit_options(tmp_path: Path, capsys):
    scheduler = FakeScheduler()
    app = sync_app(tmp_path, scheduler)
    app.vault.initialize(tmp_path / "vault")
    args = build_parser().parse_args(
        (
            "auto",
            "install",
            "--every",
            "11",
            "--from",
            "codex",
            "--home",
            str(tmp_path / "home"),
            "--include-content",
        )
    )

    assert dispatch(args, app) == 0

    installed = scheduler.installs[0][0]
    assert installed.interval_minutes == 11
    assert installed.providers == (AgentProvider.CODEX,)
    assert installed.include_content
    assert "installed" in capsys.readouterr().out


def sync_app(tmp_path: Path, scheduler: FakeScheduler | None = None):
    return create_app(
        WorkAlmanacConfig(
            state_dir=tmp_path / "state",
            vault_path=None,
        ),
        scheduler_adapter=scheduler,
    )


def write_codex_transcript(home: Path, workspace: Path) -> Path:
    transcript = home / ".codex/sessions/2026/07/27/codex.jsonl"
    transcript.parent.mkdir(parents=True)
    lines = (
        {
            "timestamp": "2026-07-27T01:00:00Z",
            "payload": {
                "id": "codex-sync-session",
                "cwd": str(workspace),
                "thread_source": "user",
            },
        },
        {
            "timestamp": "2026-07-27T01:01:00Z",
            "payload": {
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Keep this decision"}],
                }
            },
        },
        {
            "timestamp": "2026-07-27T01:02:00Z",
            "payload": {
                "item": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": "Stored incrementally"}
                    ],
                }
            },
        },
    )
    transcript.write_text(
        "".join(json.dumps(line) + "\n" for line in lines),
        encoding="utf-8",
    )
    return transcript
