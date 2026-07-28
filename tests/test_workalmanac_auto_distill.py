from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from workalmanac.app import create_app
from workalmanac.cli import build_parser, dispatch
from workalmanac.integrations.auto_distillation.windows import (
    scheduled_auto_distill_action,
)
from workalmanac.services.auto_distillation.models import AutoDistillSettings
from workalmanac.services.curators.models import (
    ContentAccess,
    CuratorReadiness,
    CuratorRunRequest,
    CuratorRunResult,
    CuratorRunStatus,
)
from workalmanac.services.vault import snapshot as vault_snapshot
from workalmanac.settings import WorkAlmanacConfig


class FakeAutoDistillScheduler:
    task_name = "WorkAlmanac Test Auto Distill"

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
            "--allow-remote-content",
        )
    )

    assert dispatch(install, app) == 0

    settings, state_dir = scheduler.installs[0]
    assert settings.interval_minutes == 60
    assert settings.limit == 1
    assert settings.content_access is ContentAccess.SELECTED_REMOTE
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
    assert app.sessions.get(second.session_id).distilled_at is not None
    assert app.sessions.get(first.session_id).distilled_at is None
    assert app.auto_distillation.settings().sessions_reserved == 1

    status = build_parser().parse_args(("auto-distill", "status"))
    assert dispatch(status, app) == 0
    remove = build_parser().parse_args(("auto-distill", "remove"))
    assert dispatch(remove, app) == 0
    assert scheduler.removals == 1
    assert not (tmp_path / "state/auto-distill.json").exists()
    output = capsys.readouterr().out
    assert "Automatic distillation is installed" in output
    assert "Automatic distill succeeded for 1 session(s)" in output
    assert "Retained Wiki pages were kept" in output


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
):
    action = scheduled_auto_distill_action(tmp_path / "Private State")

    assert "-m workalmanac.cli" in action
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
        WorkAlmanacConfig(
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
