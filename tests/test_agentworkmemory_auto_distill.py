import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from filelock import FileLock
from pydantic import ValidationError

from agentworkmemory.app import create_app
from agentworkmemory.cli import build_parser, dispatch, main
from agentworkmemory.integrations.auto_distillation.windows import (
    scheduled_auto_distill_action,
)
from agentworkmemory.services.auto_distillation.models import AutoDistillSettings
from agentworkmemory.services.curators.models import (
    ContentAccess,
    CuratorReadiness,
    CuratorRunRequest,
    CuratorRunResult,
    CuratorRunStatus,
    ReasoningEffort,
)
from agentworkmemory.services.vault import snapshot as vault_snapshot
from agentworkmemory.settings import AgentWorkMemoryConfig


class FakeAutoDistillScheduler:
    task_name = "AgentWorkMemory Test Auto Distill"

    def __init__(self):
        self.is_available = True
        self.is_installed = False
        self.installs: list[tuple[AutoDistillSettings, Path]] = []
        self.removals = 0

    def available(self) -> bool:
        return self.is_available

    def install(self, settings: AutoDistillSettings, state_dir: Path) -> None:
        self.installs.append((settings, state_dir))
        self.is_installed = True

    def installed(self) -> bool:
        return self.is_installed

    def next_run_at(self) -> datetime | None:
        return None

    def remove(self) -> None:
        self.removals += 1
        self.is_installed = False


class FakeCurator:
    runtime = "codex"

    def __init__(
        self,
        status: CuratorRunStatus = CuratorRunStatus.SUCCEEDED,
    ):
        self.status = status
        self.requests: list[CuratorRunRequest] = []

    def check(self) -> CuratorReadiness:
        return CuratorReadiness(
            runtime=self.runtime,
            available=True,
            message="ready",
        )

    def run(self, request: CuratorRunRequest) -> CuratorRunResult:
        self.requests.append(request)
        return CuratorRunResult(
            runtime=self.runtime,
            status=self.status,
            output_text="no durable changes",
        )


def test_auto_distill_settings_accept_a_large_bounded_backlog():
    settings = AutoDistillSettings(
        interval_minutes=10,
        limit=1,
        runtime="codex",
        content_access=ContentAccess.SELECTED_REMOTE,
        expires_at=datetime.now(UTC) + timedelta(days=30),
        max_sessions_total=439,
    )

    assert settings.max_sessions_total == 439


def test_auto_distill_settings_preserve_model_and_reasoning_effort():
    settings = AutoDistillSettings(
        interval_minutes=10,
        limit=1,
        runtime="codex",
        model="gpt-5.6-luna",
        effort=ReasoningEffort.XHIGH,
        content_access=ContentAccess.SELECTED_REMOTE,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        max_sessions_total=3,
    )

    assert settings.model == "gpt-5.6-luna"
    assert settings.effort is ReasoningEffort.XHIGH


def test_auto_distill_settings_reject_an_effectively_unbounded_grant():
    with pytest.raises(ValidationError):
        AutoDistillSettings(
            interval_minutes=10,
            limit=1,
            runtime="codex",
            content_access=ContentAccess.SELECTED_REMOTE,
            expires_at=datetime.now(UTC) + timedelta(days=30),
            max_sessions_total=1001,
        )


def test_auto_distill_cli_installs_runs_and_removes_bounded_remote_grant(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    scheduler = FakeAutoDistillScheduler()
    curator = FakeCurator()
    app = auto_distill_app(tmp_path, scheduler, curator)
    app.vault.initialize(tmp_path / "vault")
    first = add_note(app, "First pending decision.")
    second = add_note(app, "Second pending decision.")
    install = build_parser().parse_args(
        (
            "auto-distill",
            "install",
            "--every",
            "60",
            "--limit",
            "1",
            "--using",
            "codex",
            "--model",
            "gpt-5.6-luna",
            "--effort",
            "max",
            "--allow-remote-content",
        )
    )

    assert dispatch(install, app) == 0

    settings, state_dir = scheduler.installs[0]
    assert settings.interval_minutes == 60
    assert settings.limit == 1
    assert settings.content_access is ContentAccess.SELECTED_REMOTE
    assert settings.model == "gpt-5.6-luna"
    assert settings.effort is ReasoningEffort.MAX
    assert settings.installed_at is not None
    assert settings.max_sessions_total == 24
    assert settings.sessions_reserved == 0
    assert settings.expires_at > datetime.now(UTC)
    assert state_dir == tmp_path / "state"
    stored = app.auto_distillation.settings()
    assert stored == settings
    assert "First pending decision" not in (
        tmp_path / "state/auto-distill.json"
    ).read_text(encoding="utf-8")

    run = build_parser().parse_args(("auto-distill", "run"))
    assert dispatch(run, app) == 0
    assert len(curator.requests) == 1
    assert curator.requests[0].content_access is ContentAccess.SELECTED_REMOTE
    assert curator.requests[0].model == "gpt-5.6-luna"
    assert curator.requests[0].effort is ReasoningEffort.MAX
    assert app.sessions.get(second.session_id).distilled_at is not None
    assert app.sessions.get(first.session_id).distilled_at is None
    assert app.auto_distillation.settings().sessions_reserved == 1

    status = build_parser().parse_args(("auto-distill", "status"))
    assert dispatch(status, app) == 0
    remove = build_parser().parse_args(("auto-distill", "remove"))
    assert dispatch(remove, app) == 0
    assert scheduler.removals == 1
    assert not (tmp_path / "state/auto-distill.json").exists()
    captured = capsys.readouterr()
    assert "Automatic distillation is installed" in captured.out
    assert "Automatic distill succeeded for 1 session(s)" in captured.out
    assert "Retained Wiki pages were kept" in captured.out
    assert "Automatic distillation started" in captured.err
    assert "Starting Wiki distillation" in captured.err
    assert "Automatic distillation command finished after" in captured.err
    assert "Codex step" not in captured.err


def test_auto_distill_configure_preserves_the_existing_standing_grant(
    tmp_path: Path,
):
    scheduler = FakeAutoDistillScheduler()
    curator = FakeCurator()
    app = auto_distill_app(tmp_path, scheduler, curator)
    expires_at = datetime.now(UTC) + timedelta(days=2)
    app.auto_distillation.install(
        AutoDistillSettings(
            interval_minutes=60,
            limit=2,
            runtime="codex",
            model="gpt-5.5",
            content_access=ContentAccess.SELECTED_REMOTE,
            expires_at=expires_at,
            max_sessions_total=9,
            sessions_reserved=4,
        )
    )

    args = build_parser().parse_args(
        (
            "auto-distill",
            "configure",
            "--model",
            "gpt-5.6-luna",
            "--effort",
            "extra-high",
            "--limit",
            "10",
            "--max-total",
            "506",
        )
    )

    assert dispatch(args, app) == 0
    settings = app.auto_distillation.settings()
    assert settings.model == "gpt-5.6-luna"
    assert settings.effort is ReasoningEffort.XHIGH
    assert settings.interval_minutes == 60
    assert settings.limit == 10
    assert settings.expires_at == expires_at
    assert settings.max_sessions_total == 506
    assert settings.sessions_reserved == 4
    assert len(scheduler.installs) == 1


def test_auto_distill_install_requires_explicit_standing_content_grant(
    tmp_path: Path,
):
    scheduler = FakeAutoDistillScheduler()
    curator = FakeCurator()
    app = auto_distill_app(tmp_path, scheduler, curator)
    app.vault.initialize(tmp_path / "vault")
    args = build_parser().parse_args(
        ("auto-distill", "install", "--using", "codex")
    )

    with pytest.raises(ValueError, match="explicit local or remote"):
        dispatch(args, app)

    assert scheduler.installs == []


def test_auto_distill_cli_reports_database_contention_without_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    def fail_create_app(_config):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("agentworkmemory.cli.create_app", fail_create_app)

    assert main(("--state-dir", str(tmp_path), "auto-distill", "run")) == 1

    error = capsys.readouterr().err
    assert "error: database is locked" in error
    assert "Traceback" not in error


def test_auto_distill_run_with_empty_queue_is_a_successful_noop(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    scheduler = FakeAutoDistillScheduler()
    curator = FakeCurator()
    app = auto_distill_app(tmp_path, scheduler, curator)
    app.vault.initialize(tmp_path / "vault")
    app.auto_distillation.install(
        AutoDistillSettings(
            interval_minutes=60,
            limit=1,
            runtime="codex",
            content_access=ContentAccess.SELECTED_REMOTE,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            max_sessions_total=3,
        )
    )

    args = build_parser().parse_args(("auto-distill", "run"))

    assert dispatch(args, app) == 0
    assert curator.requests == []
    assert "No captured sessions" in capsys.readouterr().out


def test_auto_distill_waits_for_sync_then_continues(
    tmp_path: Path,
):
    scheduler = FakeAutoDistillScheduler()
    curator = FakeCurator()
    app = auto_distill_app(tmp_path, scheduler, curator)
    app.vault.initialize(tmp_path / "vault")
    add_note(app, "Pending while sync is active.")
    app.auto_distillation.install(
        AutoDistillSettings(
            interval_minutes=60,
            limit=1,
            runtime="codex",
            content_access=ContentAccess.SELECTED_REMOTE,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            max_sessions_total=3,
        )
    )
    lock_acquired = threading.Event()
    release_lock = threading.Event()

    def hold_sync_lock() -> None:
        with FileLock(tmp_path / "state" / "sync.lock"):
            lock_acquired.set()
            release_lock.wait(timeout=3)

    holder = threading.Thread(target=hold_sync_lock)
    holder.start()
    assert lock_acquired.wait(timeout=1)
    progress: list[str] = []

    def record_progress(message: str) -> None:
        progress.append(message)
        if message.startswith("Synchronization is running"):
            release_lock.set()

    receipt = app.auto_distill.run(
        progress=record_progress,
        sync_wait_seconds=2,
    )
    holder.join(timeout=1)

    assert receipt.state.value == "succeeded"
    assert any(message.startswith("Synchronization is running") for message in progress)
    assert any(message.startswith("Synchronization finished") for message in progress)
    assert app.auto_distillation.settings().sessions_reserved == 1
    assert len(curator.requests) == 1


def test_auto_distill_sync_wait_timeout_does_not_reserve_remote_grant(
    tmp_path: Path,
):
    scheduler = FakeAutoDistillScheduler()
    curator = FakeCurator()
    app = auto_distill_app(tmp_path, scheduler, curator)
    app.vault.initialize(tmp_path / "vault")
    add_note(app, "Pending while sync is active.")
    app.auto_distillation.install(
        AutoDistillSettings(
            interval_minutes=60,
            limit=1,
            runtime="codex",
            content_access=ContentAccess.SELECTED_REMOTE,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            max_sessions_total=3,
        )
    )
    lock = FileLock(tmp_path / "state" / "sync.lock")
    progress: list[str] = []

    with lock:
        receipt = app.auto_distill.run(
            progress=progress.append,
            sync_wait_seconds=0,
        )

    assert receipt.state.value == "sync-wait-expired"
    assert progress[-1] == "Synchronization did not finish before the wait limit."
    assert app.auto_distillation.settings().sessions_reserved == 0
    assert curator.requests == []


def test_auto_distill_skips_when_another_distillation_is_running(
    tmp_path: Path,
):
    scheduler = FakeAutoDistillScheduler()
    curator = FakeCurator()
    app = auto_distill_app(tmp_path, scheduler, curator)
    app.vault.initialize(tmp_path / "vault")
    add_note(app, "Pending behind another distillation.")
    app.auto_distillation.install(
        AutoDistillSettings(
            interval_minutes=60,
            limit=1,
            runtime="codex",
            content_access=ContentAccess.SELECTED_REMOTE,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            max_sessions_total=3,
        )
    )
    progress: list[str] = []

    with FileLock(tmp_path / "state" / "auto-distill.lock"):
        receipt = app.auto_distill.run(progress=progress.append)

    assert receipt.state.value == "distillation-running"
    assert progress == ["Another Wiki distillation is already running."]
    assert app.auto_distillation.settings().sessions_reserved == 0
    assert curator.requests == []


def test_auto_distill_stops_after_bounded_standing_grant(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    scheduler = FakeAutoDistillScheduler()
    curator = FakeCurator()
    app = auto_distill_app(tmp_path, scheduler, curator)
    app.vault.initialize(tmp_path / "vault")
    add_note(app, "First pending.")
    add_note(app, "Second pending.")
    app.auto_distillation.install(
        AutoDistillSettings(
            interval_minutes=60,
            limit=1,
            runtime="codex",
            content_access=ContentAccess.SELECTED_REMOTE,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            max_sessions_total=1,
        )
    )
    run = build_parser().parse_args(("auto-distill", "run"))

    assert dispatch(run, app) == 0
    assert dispatch(run, app) == 0

    assert len(curator.requests) == 1
    assert app.auto_distillation.settings().sessions_reserved == 1
    assert "expired or exhausted" in capsys.readouterr().out


def test_failed_auto_distill_attempt_still_consumes_standing_grant(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    scheduler = FakeAutoDistillScheduler()
    curator = FakeCurator(CuratorRunStatus.FAILED)
    app = auto_distill_app(tmp_path, scheduler, curator)
    app.vault.initialize(tmp_path / "vault")
    add_note(app, "Sensitive pending evidence.")
    app.auto_distillation.install(
        AutoDistillSettings(
            interval_minutes=60,
            limit=1,
            runtime="codex",
            content_access=ContentAccess.SELECTED_REMOTE,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            max_sessions_total=1,
        )
    )
    run = build_parser().parse_args(("auto-distill", "run"))

    with pytest.raises(RuntimeError, match="ended with failed"):
        dispatch(run, app)
    assert app.auto_distillation.settings().sessions_reserved == 1

    assert dispatch(run, app) == 0
    assert len(curator.requests) == 1
    assert "expired or exhausted" in capsys.readouterr().out


def test_operator_can_refund_a_verified_pre_model_failure(tmp_path: Path):
    scheduler = FakeAutoDistillScheduler()
    curator = FakeCurator()
    app = auto_distill_app(tmp_path, scheduler, curator)
    app.auto_distillation.install(
        AutoDistillSettings(
            interval_minutes=60,
            limit=1,
            runtime="codex",
            content_access=ContentAccess.SELECTED_REMOTE,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            max_sessions_total=3,
            sessions_reserved=2,
        )
    )

    refunded = app.auto_distillation.refund_sessions(1)

    assert refunded.sessions_reserved == 1
    with pytest.raises(ValueError, match="more sessions"):
        app.auto_distillation.refund_sessions(2)


def test_local_preflight_failure_does_not_consume_standing_grant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    scheduler = FakeAutoDistillScheduler()
    curator = FakeCurator()
    app = auto_distill_app(tmp_path, scheduler, curator)
    vault = app.vault.initialize(tmp_path / "vault")
    add_note(app, "Pending evidence stays outside the curator snapshot.")
    (vault / "projects" / "too-large.md").write_bytes(b"x" * 8192)
    monkeypatch.setattr(vault_snapshot, "MAX_SNAPSHOT_BYTES", 4096)
    app.auto_distillation.install(
        AutoDistillSettings(
            interval_minutes=60,
            limit=1,
            runtime="codex",
            content_access=ContentAccess.SELECTED_REMOTE,
            expires_at=datetime.now(UTC) + timedelta(days=1),
            max_sessions_total=1,
        )
    )

    with pytest.raises(ValueError, match="Vault is too large"):
        app.auto_distill.run()

    assert app.auto_distillation.settings().sessions_reserved == 0
    assert curator.requests == []


def test_scheduled_auto_distill_action_contains_only_private_state_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "agentworkmemory.integrations.auto_distillation.windows.background_python_executable",
        lambda: r"C:\AWM Runtime\pythonw.exe",
    )
    action = scheduled_auto_distill_action(tmp_path / "Private State")

    assert "pythonw.exe" in action
    assert "-m agentworkmemory.scheduled" in action
    assert "auto-distill run" in action
    assert str(tmp_path / "Private State") in action
    assert "--allow-remote-content" not in action
    assert "--using" not in action
    assert "ses_" not in action


def auto_distill_app(
    tmp_path: Path,
    scheduler: FakeAutoDistillScheduler,
    curator: FakeCurator,
):
    return create_app(
        AgentWorkMemoryConfig(
            state_dir=tmp_path / "state",
            vault_path=None,
        ),
        curator_adapters=(curator,),
        auto_distill_scheduler_adapter=scheduler,
    )


def add_note(app, text: str):
    session = app.sessions.add_manual_note(text)
    app.vault.refresh_session(
        session,
        app.sessions.events(session.session_id),
    )
    return session
