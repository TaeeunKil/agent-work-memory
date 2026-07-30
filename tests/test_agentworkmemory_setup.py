import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from agentworkmemory.app import create_app
from agentworkmemory.cli import build_parser, dispatch
from agentworkmemory.services.automation.models import AutoSyncSettings
from agentworkmemory.services.curators.models import (
    CuratorReadiness,
    CuratorRunRequest,
    CuratorRunResult,
    CuratorRunStatus,
)
from agentworkmemory.services.diagnostics.models import DiagnosticStatus
from agentworkmemory.services.sessions.models import AgentProvider
from agentworkmemory.settings import AgentWorkMemoryConfig
from agentworkmemory.workflows.import_legacy import ImportLegacyAlmanac
from agentworkmemory.workflows.import_legacy.service import legacy_namespace
from agentworkmemory.workflows.setup import SetupAgentWorkMemory


class SetupScheduler:
    task_name = "AgentWorkMemory Setup Test"

    def __init__(self):
        self.settings: AutoSyncSettings | None = None

    def available(self) -> bool:
        return True

    def install(self, settings: AutoSyncSettings, state_dir: Path) -> None:
        self.settings = settings

    def installed(self) -> bool:
        return self.settings is not None

    def next_run_at(self) -> datetime | None:
        return None

    def remove(self) -> None:
        self.settings = None


class SetupCurator:
    runtime = "setup-local"

    def check(self) -> CuratorReadiness:
        return CuratorReadiness(
            runtime=self.runtime,
            available=True,
            message="setup curator ready",
        )

    def run(self, request: CuratorRunRequest) -> CuratorRunResult:
        return CuratorRunResult(
            runtime=self.runtime,
            status=CuratorRunStatus.SUCCEEDED,
            output_text="no-op",
        )


def test_setup_initializes_collects_and_installs_explicit_automation(
    tmp_path: Path,
):
    scheduler = SetupScheduler()
    app = setup_app(tmp_path, scheduler)
    home = tmp_path / "home"
    write_codex_transcript(home, tmp_path / "project")

    result = app.setup.run(
        SetupAgentWorkMemory(
            vault_path=tmp_path / "vault",
            home=home,
            providers=(AgentProvider.CODEX,),
            include_content=True,
            auto_interval_minutes=6,
        )
    )

    assert result.vault_path == (tmp_path / "vault").resolve()
    assert result.sync.events_added == 2
    assert result.automation_installed
    assert scheduler.settings is not None
    assert scheduler.settings.interval_minutes == 6
    assert scheduler.settings.include_content
    assert (result.vault_path / "Home.md").is_file()
    assert len(app.sessions.list()) == 1


def test_setup_cli_keeps_content_and_automation_explicit(tmp_path: Path, capsys):
    scheduler = SetupScheduler()
    app = setup_app(tmp_path, scheduler)
    args = build_parser().parse_args(
        (
            "setup",
            str(tmp_path / "vault"),
            "--home",
            str(tmp_path / "home"),
            "--from",
            "codex",
            "--include-content",
            "--auto",
            "--every",
            "9",
        )
    )

    assert dispatch(args, app) == 0

    assert scheduler.settings is not None
    assert scheduler.settings.interval_minutes == 9
    assert scheduler.settings.include_content
    assert "Agent Work Memory ready" in capsys.readouterr().out


def test_legacy_almanac_import_is_isolated_searchable_and_idempotent(
    tmp_path: Path,
):
    app = setup_app(tmp_path, SetupScheduler())
    vault = app.vault.initialize(tmp_path / "vault")
    page = tmp_path / "legacy-repo" / ".almanac" / "pages" / "decisions" / "why.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "# Legacy rationale\n\nKeep the original repository decision.\n",
        encoding="utf-8",
    )
    ignored = page.parent / "private.json"
    ignored.write_text('{"secret": true}', encoding="utf-8")
    request = ImportLegacyAlmanac(source=tmp_path / "legacy-repo")

    first = app.import_legacy.run(request)
    second = app.import_legacy.run(request)

    assert first.files_discovered == 1
    assert first.files_copied == 1
    assert second.files_copied == 0
    assert second.files_unchanged == 1
    imported = vault / first.target / "decisions" / "why.md"
    assert imported.read_text(encoding="utf-8") == page.read_text(encoding="utf-8")
    assert not (vault / first.target / "decisions" / "private.json").exists()
    assert any(
        result.identity == imported.relative_to(vault).as_posix()
        for result in app.search.find("original repository decision")
    )
    assert any(wiki_page.category == "imports" for wiki_page in app.wiki.pages())
    assert (vault / "imports" / "_index.md").is_file()


def test_invalid_legacy_bundle_leaves_no_partially_imported_pages(tmp_path: Path):
    app = setup_app(tmp_path, SetupScheduler())
    vault = app.vault.initialize(tmp_path / "vault")
    pages = tmp_path / "legacy-repo" / ".almanac" / "pages"
    pages.mkdir(parents=True)
    (pages / "a-valid.md").write_text("# Valid\n", encoding="utf-8")
    (pages / "z-invalid.md").write_bytes(b"\xff")

    with pytest.raises(UnicodeDecodeError):
        app.import_legacy.run(ImportLegacyAlmanac(source=tmp_path / "legacy-repo"))

    imported = vault / "imports" / "repository-almanacs"
    assert not tuple(imported.rglob("a-valid.md"))


def test_legacy_namespace_uses_platform_path_case_rules(tmp_path: Path):
    repository = tmp_path / "LegacyRepo"

    if os.name == "nt":
        assert legacy_namespace(repository) == legacy_namespace(
            Path(str(repository).upper())
        )
    else:
        assert legacy_namespace(repository) != legacy_namespace(
            Path(str(repository).upper())
        )


def test_doctor_reports_local_state_without_absolute_transcript_paths(
    tmp_path: Path,
):
    scheduler = SetupScheduler()
    app = setup_app(tmp_path, scheduler)
    home = tmp_path / "home"
    app.vault.initialize(tmp_path / "vault")
    write_codex_transcript(home, tmp_path / "project")

    checks = app.diagnostics.run(home, include_runtimes=True)

    by_name = {check.name: check for check in checks}
    assert by_name["vault"].status is DiagnosticStatus.OK
    assert by_name["database"].status is DiagnosticStatus.OK
    assert by_name["transcripts:codex"].status is DiagnosticStatus.OK
    assert by_name["transcripts:claude"].status is DiagnosticStatus.WARNING
    assert by_name["runtime:setup-local"].status is DiagnosticStatus.OK
    assert str(home) not in " ".join(check.message for check in checks)


def setup_app(tmp_path: Path, scheduler: SetupScheduler):
    return create_app(
        AgentWorkMemoryConfig(state_dir=tmp_path / "state", vault_path=None),
        scheduler_adapter=scheduler,
        curator_adapters=(SetupCurator(),),
    )


def write_codex_transcript(home: Path, workspace: Path) -> Path:
    transcript = home / ".codex/sessions/2026/07/27/setup.jsonl"
    transcript.parent.mkdir(parents=True)
    lines = (
        {
            "timestamp": "2026-07-27T01:00:00Z",
            "payload": {
                "id": "codex-setup-session",
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
                    "content": [{"type": "input_text", "text": "Set up memory"}],
                }
            },
        },
        {
            "timestamp": "2026-07-27T01:02:00Z",
            "payload": {
                "item": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Setup complete"}],
                }
            },
        },
    )
    transcript.write_text(
        "".join(json.dumps(line) + "\n" for line in lines),
        encoding="utf-8",
    )
    return transcript
