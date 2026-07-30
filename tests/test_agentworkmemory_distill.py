import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentworkmemory.app import create_app
from agentworkmemory.cli import main
from agentworkmemory.integrations.curators import yoke as yoke_curator
from agentworkmemory.integrations.curators.hidden_codex import hidden_run_command
from agentworkmemory.integrations.curators.yoke import (
    YokeCuratorAdapter,
    apply_windows_curator_output,
    curator_surface,
    run_options,
    standalone_codex_executable,
)
from agentworkmemory.integrations.curators.yoke_utf8 import enable_yoke_codex_utf8
from agentworkmemory.integrations.processes import WINDOWS_CREATE_NO_WINDOW
from agentworkmemory.services.curators.models import (
    ContentAccess,
    CuratorReadiness,
    CuratorRunRequest,
    CuratorRunResult,
    CuratorRunStatus,
)
from agentworkmemory.services.distillation.models import (
    DistillStatus,
    SessionDistillDisposition,
)
from agentworkmemory.services.distillation.outcomes import (
    classify_session_outcomes,
)
from agentworkmemory.services.wiki.models import WikiPage
from agentworkmemory.settings import AgentWorkMemoryConfig
from agentworkmemory.workflows.distill import DistillSessions


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

    receipt = app.distill.run(
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
    assert receipt.session_outcomes[0].disposition is (
        SessionDistillDisposition.NO_DURABLE_KNOWLEDGE
    )
    assert app.distillation.get(receipt.run_id) == receipt


def test_distill_outcomes_classify_created_merged_covered_and_noop():
    created = "ses_created"
    merged = "ses_merged"
    covered = "ses_covered"
    skipped = "ses_skipped"
    before = (
        wiki_page("projects/existing.md", merged),
        wiki_page("decisions/covered.md", covered),
    )
    after = (
        wiki_page("projects/existing.md", merged),
        wiki_page("decisions/covered.md", covered),
        wiki_page("procedures/new.md", created),
    )

    outcomes = classify_session_outcomes(
        (created, merged, covered, skipped),
        before=before,
        after=after,
        changed_files=(
            Path("projects/existing.md"),
            Path("procedures/new.md"),
        ),
    )

    assert [outcome.disposition for outcome in outcomes] == [
        SessionDistillDisposition.CREATED,
        SessionDistillDisposition.MERGED,
        SessionDistillDisposition.ALREADY_COVERED,
        SessionDistillDisposition.NO_DURABLE_KNOWLEDGE,
    ]
    assert outcomes[0].pages == (Path("procedures/new.md"),)
    assert outcomes[-1].pages == ()


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


def test_batch_distill_divides_evidence_budget_across_sessions(
    tmp_path: Path,
):
    adapter = FakeCuratorAdapter()
    app = distill_app(tmp_path, adapter)
    app.vault.initialize(tmp_path / "vault")
    first = note_session(app, "A" * 120_000)
    second = note_session(app, "SECOND-SESSION-EVIDENCE")

    app.distill.run(
        DistillSessions(
            session_ids=(first.session_id, second.session_id),
            runtime=adapter.runtime,
            content_access=ContentAccess.SELECTED_LOCAL,
        )
    )

    prompt = adapter.requests[0].prompt
    assert "[Event excerpt truncated at curator boundary.]" in prompt
    assert "SECOND-SESSION-EVIDENCE" in prompt


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
    monkeypatch.setattr("agentworkmemory.cli.create_app", lambda config: app)

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


def test_distill_cli_selects_newest_pending_sessions_with_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    adapter = FakeCuratorAdapter()
    app = distill_app(tmp_path, adapter)
    app.vault.initialize(tmp_path / "vault")
    project = tmp_path / "project"
    oldest = note_session(app, "Old pending evidence.", cwd=project)
    middle = note_session(app, "Middle pending evidence.", cwd=project)
    newest = note_session(app, "Newest pending evidence.", cwd=project)
    metadata_only = app.sessions.remember_discovered(
        provider="codex",
        provider_session_id="metadata-only",
        cwd=None,
        source_path=tmp_path / "metadata.jsonl",
        modified_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    monkeypatch.setattr("agentworkmemory.cli.create_app", lambda config: app)

    exit_code = main(
        (
            "--state-dir",
            str(tmp_path / "state"),
            "distill",
            "--pending",
            "--limit",
            "2",
            "--using",
            adapter.runtime,
            "--allow-remote-content",
        )
    )

    assert exit_code == 0
    assert app.sessions.get(newest.session_id).distilled_at is not None
    assert app.sessions.get(middle.session_id).distilled_at is not None
    assert app.sessions.get(oldest.session_id).distilled_at is None
    assert app.sessions.get(metadata_only.session_id).distilled_at is None
    output = capsys.readouterr().out
    assert "Selected 2 pending session(s)" in output
    assert newest.session_id in output
    assert middle.session_id in output


def test_distill_cli_pending_empty_queue_is_a_noop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    adapter = FakeCuratorAdapter()
    app = distill_app(tmp_path, adapter)
    app.vault.initialize(tmp_path / "vault")
    monkeypatch.setattr("agentworkmemory.cli.create_app", lambda config: app)

    exit_code = main(("distill", "--pending", "--using", adapter.runtime))

    assert exit_code == 0
    assert adapter.requests == []
    assert "No captured sessions" in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments, message",
    (
        (("distill",), "session ids or --pending"),
        (("distill", "ses_example", "--pending"), "cannot be combined"),
        (("distill", "ses_example", "--limit", "2"), "requires --pending"),
        (("distill", "--pending", "--limit", "0"), "between 1 and 20"),
        (("distill", "--pending", "--limit", "21"), "between 1 and 20"),
    ),
)
def test_distill_cli_rejects_invalid_selection_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: tuple[str, ...],
    message: str,
):
    adapter = FakeCuratorAdapter()
    app = distill_app(tmp_path, adapter)
    app.vault.initialize(tmp_path / "vault")
    monkeypatch.setattr("agentworkmemory.cli.create_app", lambda config: app)

    assert main(arguments) == 1

    assert message in capsys.readouterr().err
    assert adapter.requests == []


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


def test_windows_yoke_curator_uses_standalone_codex_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    vault = tmp_path / "vault"
    vault.mkdir()
    adapter = YokeCuratorAdapter("codex", tmp_path / "state/curators/codex")
    monkeypatch.setattr(
        "agentworkmemory.integrations.curators.yoke.sys",
        SimpleNamespace(platform="win32"),
    )

    assert curator_surface("codex", "win32") == "codex_cli"
    assert curator_surface("codex", "linux") == "codex_app_server"
    harness = adapter.harness(vault)
    request = CuratorRunRequest(
        runtime="codex",
        vault_path=vault,
        prompt="Maintain durable Wiki knowledge.",
        content_access=ContentAccess.SELECTED_REMOTE,
    )
    options = run_options(request, surface="codex_cli")

    assert harness.surface == "codex_cli"
    assert "Do not create or edit Vault Markdown directly" in harness.agent.instructions
    assert ".awm-curator-output.json" in harness.agent.instructions
    assert options.provider is None
    assert harness.plan(options).ok


def test_windows_curator_output_is_written_by_parent_process(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()

    written = apply_windows_curator_output(
        vault,
        json.dumps(
            {
                "files": [
                    {
                        "path": "decisions/parent-writer.md",
                        "content": "# Parent writer\n",
                    }
                ]
            }
        ),
    )

    assert written == (Path("decisions/parent-writer.md"),)
    assert (vault / written[0]).read_text(encoding="utf-8") == "# Parent writer\n"


def test_windows_yoke_curator_applies_json_handoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    vault = tmp_path / "vault"
    vault.mkdir()
    adapter = YokeCuratorAdapter("codex", tmp_path / "state/curators/codex")

    class HandoffHarness:
        def run_sync(self, prompt, options):
            assert prompt == "Maintain durable Wiki knowledge."
            assert (vault / ".awm-curator-output.json").is_file()
            (vault / ".awm-curator-output.json").write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": "projects/handoff.md",
                                "content": "# Handoff\n",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(
                status="succeeded",
                output="wrote one page",
                failure=None,
                provider_session_id="codex-handoff",
            )

    monkeypatch.setattr(
        "agentworkmemory.integrations.curators.yoke.sys",
        SimpleNamespace(platform="win32"),
    )
    monkeypatch.setattr(adapter, "harness", lambda _cwd: HandoffHarness())

    result = adapter.run(
        CuratorRunRequest(
            runtime="codex",
            vault_path=vault,
            prompt="Maintain durable Wiki knowledge.",
            content_access=ContentAccess.SELECTED_REMOTE,
        )
    )

    assert result.status is CuratorRunStatus.SUCCEEDED
    assert (vault / "projects/handoff.md").read_text(encoding="utf-8") == "# Handoff\n"
    assert not (vault / ".awm-curator-output.json").exists()


def test_windows_yoke_repairs_handoff_permissions_before_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    vault = tmp_path / "vault"
    vault.mkdir()
    repair_calls = []

    def repair_workspace(path: Path) -> None:
        repair_calls.append(path)
        (path / ".awm-curator-output.json").write_text(
            json.dumps(
                {
                    "files": [
                        {
                            "path": "systems/repaired-handoff.md",
                            "content": "# Repaired handoff\n",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

    adapter = YokeCuratorAdapter(
        "codex",
        tmp_path / "state/curators/codex",
        workspace_permission_repair=repair_workspace,
    )

    class SandboxOwnedHandoffHarness:
        def run_sync(self, prompt, options):
            (vault / ".awm-curator-output.json").write_text(
                "sandbox-owned",
                encoding="utf-8",
            )
            return SimpleNamespace(
                status="succeeded",
                output="wrote one page",
                failure=None,
                provider_session_id="codex-repaired-handoff",
            )

    monkeypatch.setattr(
        "agentworkmemory.integrations.curators.yoke.sys",
        SimpleNamespace(platform="win32"),
    )
    monkeypatch.setattr(
        adapter,
        "harness",
        lambda _cwd: SandboxOwnedHandoffHarness(),
    )

    result = adapter.run(
        CuratorRunRequest(
            runtime="codex",
            vault_path=vault,
            prompt="Maintain durable Wiki knowledge.",
            content_access=ContentAccess.SELECTED_REMOTE,
        )
    )

    assert result.status is CuratorRunStatus.SUCCEEDED
    assert repair_calls == [vault, vault]
    assert (vault / "systems/repaired-handoff.md").read_text(
        encoding="utf-8"
    ) == "# Repaired handoff\n"
    assert not (vault / ".awm-curator-output.json").exists()


def test_windows_handoff_read_repairs_and_retries_sharing_violation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    vault = tmp_path / "vault"
    vault.mkdir()
    handoff = vault / yoke_curator.WINDOWS_CURATOR_OUTPUT
    handoff.write_text('{"files":[]}\n', encoding="utf-8")
    original_read_text = Path.read_text
    attempts = 0
    repairs = []

    def read_text(path: Path, *args, **kwargs):
        nonlocal attempts
        if path == handoff:
            attempts += 1
            if attempts == 1:
                error = OSError("handoff is still releasing")
                error.winerror = 32
                raise error
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(yoke_curator.os, "name", "nt")
    monkeypatch.setattr(Path, "read_text", read_text)
    monkeypatch.setattr(yoke_curator.time, "sleep", lambda _delay: None)

    raw = yoke_curator.read_windows_curator_output(
        handoff,
        vault_path=vault,
        permission_repair=repairs.append,
    )

    assert raw == '{"files":[]}\n'
    assert attempts == 2
    assert repairs == [vault, vault]


@pytest.mark.parametrize(
    "path",
    ("../escape.md", "C:/absolute.md"),
)
def test_windows_curator_output_rejects_paths_outside_vault(
    tmp_path: Path,
    path: str,
):
    vault = tmp_path / "vault"
    vault.mkdir()

    with pytest.raises(ValueError, match="path"):
        apply_windows_curator_output(
            vault,
            json.dumps({"files": [{"path": path, "content": "# Unsafe\n"}]}),
        )


def test_windows_yoke_curator_prefers_standalone_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    executable = (
        tmp_path / "Programs/OpenAI/Codex/bin/codex.exe"
    )
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert standalone_codex_executable() == str(executable)


def test_yoke_codex_process_uses_utf8_instead_of_windows_locale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from yoke.providers.codex_app.process import JsonRpcLineProcess

    captured = {}

    class FakeChild:
        stdin = None
        stdout = iter(())
        stderr = iter(())

        def poll(self):
            return 0

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return FakeChild()

    monkeypatch.setattr(JsonRpcLineProcess, "start", JsonRpcLineProcess.start)
    monkeypatch.setattr(
        "agentworkmemory.integrations.curators.yoke_utf8.subprocess.Popen",
        fake_popen,
    )

    enable_yoke_codex_utf8()
    JsonRpcLineProcess.start(
        "codex",
        ("app-server",),
        tmp_path,
        {"EXAMPLE": "1"},
    )

    assert captured["command"] == ("codex", "app-server")
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "strict"
    assert captured["env"]["EXAMPLE"] == "1"
    assert captured["creationflags"] == WINDOWS_CREATE_NO_WINDOW


def test_windows_codex_readiness_process_is_hidden(
    monkeypatch: pytest.MonkeyPatch,
):
    captured = {}

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return b"Logged in", b""

    async def fake_subprocess(*args, **kwargs):
        captured["args"] = args
        captured.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(
        "agentworkmemory.integrations.curators.hidden_codex."
        "asyncio.create_subprocess_exec",
        fake_subprocess,
    )

    result = asyncio.run(hidden_run_command("codex", "login", "status"))

    assert result.code == 0
    assert captured["creationflags"] == WINDOWS_CREATE_NO_WINDOW


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


def test_yoke_curator_redacts_permission_failures(
    tmp_path: Path,
    monkeypatch,
):
    (tmp_path / "vault").mkdir()

    class PermissionDeniedHarness:
        def check_sync(self):
            raise PermissionError(r"C:\private\runtime.exe")

        def run_sync(self, prompt, options):
            raise PermissionError(r"C:\private\runtime.exe")

    adapter = YokeCuratorAdapter("codex", tmp_path / "state/curators/codex")
    monkeypatch.setattr(
        adapter,
        "harness",
        lambda _cwd: PermissionDeniedHarness(),
    )

    readiness = adapter.check()
    result = adapter.run(
        CuratorRunRequest(
            runtime="codex",
            vault_path=tmp_path / "vault",
            prompt="Do not run.",
            content_access=ContentAccess.METADATA_ONLY,
        )
    )

    assert not readiness.available
    assert "PermissionError" in readiness.message
    assert r"C:\private" not in readiness.message
    assert result.status is CuratorRunStatus.FAILED
    assert result.output_text == "codex curator failed (PermissionError)"


def distill_app(tmp_path: Path, adapter: FakeCuratorAdapter):
    return create_app(
        AgentWorkMemoryConfig(
            state_dir=tmp_path / "state",
            vault_path=None,
        ),
        curator_adapters=(adapter,),
    )


def note_session(app, text: str, *, cwd: Path | None = None):
    session = app.sessions.add_manual_note(
        text,
        title="Distill test",
        cwd=cwd,
    )
    app.vault.refresh_session(
        session,
        app.sessions.events(session.session_id),
    )
    return session


def wiki_page(path: str, session_id: str) -> WikiPage:
    relative = Path(path)
    return WikiPage(
        path=relative,
        title=relative.stem,
        category=relative.parts[0],
        source_session_ids=(session_id,),
    )


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
