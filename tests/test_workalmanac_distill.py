from collections.abc import Callable
from pathlib import Path

import pytest

from workalmanac.app import create_app
from workalmanac.cli import main
from workalmanac.integrations.curators.yoke import (
    YokeCuratorAdapter,
    run_options,
)
from workalmanac.services.curators.models import (
    ContentAccess,
    CuratorReadiness,
    CuratorRunRequest,
    CuratorRunResult,
    CuratorRunStatus,
)
from workalmanac.services.distillation.models import DistillStatus
from workalmanac.settings import WorkAlmanacConfig
from workalmanac.workflows.distill import DistillSessions


class FakeCuratorAdapter:
    def __init__(
        self,
        *,
        runtime: str = "fake-local",
        status: CuratorRunStatus = CuratorRunStatus.SUCCEEDED,
        mutate: Callable[[CuratorRunRequest], None] | None = None,
    ):
        self.runtime = runtime
        self.status = status
        self.mutate = mutate
        self.requests: list[CuratorRunRequest] = []
        self.workspace_inbox_visibility: list[bool] = []

    def check(self) -> CuratorReadiness:
        return CuratorReadiness(
            runtime=self.runtime,
            available=True,
            message="ready",
        )

    def run(self, request: CuratorRunRequest) -> CuratorRunResult:
        self.requests.append(request)
        self.workspace_inbox_visibility.append((request.vault_path / "inbox").exists())
        if self.mutate is not None:
            self.mutate(request)
        return CuratorRunResult(
            runtime=self.runtime,
            status=self.status,
            output_text="updated durable knowledge",
            provider_session_id="curator-session-1",
        )


def test_distill_promotes_session_into_durable_wiki(tmp_path: Path):
    adapter = FakeCuratorAdapter(mutate=write_decision)
    app = distill_app(tmp_path, adapter)
    vault = app.vault.initialize(tmp_path / "vault")
    session = note_session(app, "Use one central writer for the Wiki.")

    receipt = app.distill.run(
        DistillSessions(
            session_ids=(session.session_id,),
            runtime=adapter.runtime,
            content_access=ContentAccess.SELECTED_LOCAL,
        )
    )

    assert receipt.status is DistillStatus.SUCCEEDED
    assert receipt.changed_files == (Path("decisions/central-writer.md"),)
    assert (vault / receipt.changed_files[0]).is_file()
    remembered = app.sessions.get(session.session_id)
    assert remembered.distilled_at is not None
    assert remembered.distill_runtime == adapter.runtime
    session_page = next((vault / "inbox/agent-sessions").glob("manual-*.md"))
    assert "Distilled:" in session_page.read_text(encoding="utf-8")
    assert any(
        result.identity == "decisions/central-writer.md"
        for result in app.search.find("single writer")
    )
    stored = app.distillation.get(receipt.run_id)
    assert stored is not None
    assert stored.session_ids == (session.session_id,)
    assert "Use one central writer" not in (stored.output_summary or "")


def test_metadata_only_prompt_withholds_event_bodies(tmp_path: Path):
    adapter = FakeCuratorAdapter()
    app = distill_app(tmp_path, adapter)
    app.vault.initialize(tmp_path / "vault")
    session = app.sessions.add_manual_note("Sensitive agent transcript body.")
    app.vault.refresh_session(
        session,
        app.sessions.events(session.session_id),
    )

    app.distill.run(
        DistillSessions(
            session_ids=(session.session_id,),
            runtime=adapter.runtime,
            content_access=ContentAccess.METADATA_ONLY,
        )
    )

    prompt = adapter.requests[0].prompt
    assert "Sensitive agent transcript body." not in prompt
    assert "Event bodies withheld" in prompt
    assert adapter.workspace_inbox_visibility == [False]


def test_selected_content_is_bounded_into_curator_prompt(tmp_path: Path):
    adapter = FakeCuratorAdapter()
    app = distill_app(tmp_path, adapter)
    app.vault.initialize(tmp_path / "vault")
    session = note_session(app, "Selected evidence reaches the local curator.")

    app.distill.run(
        DistillSessions(
            session_ids=(session.session_id,),
            runtime=adapter.runtime,
            content_access=ContentAccess.SELECTED_LOCAL,
        )
    )

    assert "Selected evidence reaches the local curator." in adapter.requests[0].prompt


def test_forbidden_inbox_change_is_rolled_back(tmp_path: Path):
    adapter = FakeCuratorAdapter(mutate=overwrite_inbox)
    app = distill_app(tmp_path, adapter)
    vault = app.vault.initialize(tmp_path / "vault")
    session = note_session(app, "Keep the evidence record immutable.")
    session_page = next((vault / "inbox/agent-sessions").glob("manual-*.md"))
    before = session_page.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="forbidden Vault path"):
        app.distill.run(
            DistillSessions(
                session_ids=(session.session_id,),
                runtime=adapter.runtime,
                content_access=ContentAccess.SELECTED_LOCAL,
            )
        )

    assert session_page.read_text(encoding="utf-8") == before
    assert app.sessions.get(session.session_id).distilled_at is None


def test_failed_curator_restores_durable_changes(tmp_path: Path):
    adapter = FakeCuratorAdapter(
        status=CuratorRunStatus.FAILED,
        mutate=write_decision,
    )
    app = distill_app(tmp_path, adapter)
    vault = app.vault.initialize(tmp_path / "vault")
    session = note_session(app, "A failed run must not leave trusted prose.")

    with pytest.raises(RuntimeError, match="ended with failed"):
        app.distill.run(
            DistillSessions(
                session_ids=(session.session_id,),
                runtime=adapter.runtime,
                content_access=ContentAccess.SELECTED_LOCAL,
            )
        )

    assert not (vault / "decisions/central-writer.md").exists()
    assert app.sessions.get(session.session_id).distilled_at is None


def test_post_run_failure_restores_applied_wiki_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    adapter = FakeCuratorAdapter(mutate=write_decision)
    app = distill_app(tmp_path, adapter)
    vault = app.vault.initialize(tmp_path / "vault")
    session = note_session(app, "Index failure must roll back the Wiki transaction.")

    def fail_refresh() -> None:
        raise RuntimeError("index failed")

    monkeypatch.setattr(app.search, "refresh", fail_refresh)

    with pytest.raises(RuntimeError, match="index failed"):
        app.distill.run(
            DistillSessions(
                session_ids=(session.session_id,),
                runtime=adapter.runtime,
                content_access=ContentAccess.SELECTED_LOCAL,
            )
        )

    assert not (vault / "decisions/central-writer.md").exists()
    assert app.sessions.get(session.session_id).distilled_at is None


def test_distill_cli_maps_explicit_remote_content_grant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    adapter = FakeCuratorAdapter()
    app = distill_app(tmp_path, adapter)
    state = tmp_path / "state"
    app.vault.initialize(tmp_path / "vault")
    session = note_session(app, "CLI-selected evidence.")
    monkeypatch.setattr("workalmanac.cli.create_app", lambda config: app)

    exit_code = main(
        (
            "--state-dir",
            str(state),
            "distill",
            session.session_id,
            "--using",
            adapter.runtime,
            "--allow-remote-content",
        )
    )

    assert exit_code == 0
    assert adapter.requests[0].content_access is ContentAccess.SELECTED_REMOTE
    assert "Distill dst_" in capsys.readouterr().out


def test_yoke_curator_is_wiki_write_only_and_offline(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    adapter = YokeCuratorAdapter("codex", tmp_path / "state/curators/codex")
    request = CuratorRunRequest(
        runtime="codex",
        vault_path=vault,
        prompt="Maintain durable Wiki knowledge.",
        content_access=ContentAccess.METADATA_ONLY,
    )

    harness = adapter.harness(vault)
    options = run_options(request)

    assert harness.agent.tools.read
    assert harness.agent.tools.write
    assert not harness.agent.tools.shell
    assert not harness.agent.tools.web
    assert not harness.agent.tools.agent
    assert harness.agent.permissions is not None
    assert not harness.agent.permissions.network
    assert options.permissions is not None
    assert not options.permissions.network
    assert options.provider is not None
    assert options.provider.codex is not None
    assert options.provider.codex.sandbox == "workspace-write"
    assert options.provider.codex.approval == "never"


def test_remote_yoke_curator_rejects_selected_local_content(tmp_path: Path):
    adapter = YokeCuratorAdapter("claude", tmp_path / "state/curators/claude")

    with pytest.raises(ValueError, match="selected-local"):
        adapter.run(
            CuratorRunRequest(
                runtime="claude",
                vault_path=tmp_path / "vault",
                prompt="Do not run.",
                content_access=ContentAccess.SELECTED_LOCAL,
            )
        )


def distill_app(tmp_path: Path, adapter: FakeCuratorAdapter):
    return create_app(
        WorkAlmanacConfig(
            state_dir=tmp_path / "state",
            vault_path=None,
        ),
        curator_adapters=(adapter,),
    )


def note_session(app, text: str):
    session = app.sessions.add_manual_note(text, title="Distill test")
    app.vault.refresh_session(
        session,
        app.sessions.events(session.session_id),
    )
    return session


def write_decision(request: CuratorRunRequest) -> None:
    path = request.vault_path / "decisions/central-writer.md"
    path.write_text(
        """---
title: Central Writer
sources:
  - id: selected-session
    type: conversation
    session_id: ses_example
---
# Central Writer

Use a single writer for durable Markdown knowledge. [@selected-session]
""",
        encoding="utf-8",
    )


def overwrite_inbox(request: CuratorRunRequest) -> None:
    page = request.vault_path / "inbox/agent-sessions/corrupted.md"
    page.parent.mkdir(parents=True)
    page.write_text("# Corrupted record\n", encoding="utf-8")
