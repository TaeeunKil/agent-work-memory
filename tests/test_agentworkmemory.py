import json
import tomllib
from pathlib import Path

from agentworkmemory.app import create_app
from agentworkmemory.cli import main
from agentworkmemory.services.sessions.models import AgentProvider
from agentworkmemory.settings import AgentWorkMemoryConfig
from agentworkmemory.workflows.collect import CollectAgentRecords

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_manual_note_becomes_searchable_wiki_record(
    tmp_path: Path,
    monkeypatch,
):
    app = isolated_app(tmp_path)
    vault = app.vault.initialize(tmp_path / "vault")

    session = app.sessions.add_manual_note(
        "Use one central writer for the Markdown Vault.",
        title="Central writer decision",
        cwd=tmp_path / "unregistered-workspace",
    )
    page = app.vault.refresh_session(
        session,
        app.sessions.events(session.session_id),
    )

    assert page.is_relative_to(vault)
    assert "Use one central writer" in page.read_text(encoding="utf-8")
    results = app.search.find("central writer")
    assert any(result.identity == session.session_id for result in results)
    assert any(result.identity.endswith(".md") for result in results)

    refresh_calls = 0
    original_refresh = app.search.refresh

    def count_refresh(signature=None) -> None:
        nonlocal refresh_calls
        refresh_calls += 1
        original_refresh(signature)

    monkeypatch.setattr(app.search, "refresh", count_refresh)
    app.search.find("central writer")
    assert refresh_calls == 0

    second = app.sessions.add_manual_note(
        "Remember the separate reader boundary.",
        title="Reader boundary",
    )
    app.vault.refresh_session(second, app.sessions.events(second.session_id))

    assert app.search.find("separate reader")
    assert refresh_calls == 1


def test_collects_codex_and_claude_without_repository_registration(tmp_path: Path):
    app = isolated_app(tmp_path)
    vault = app.vault.initialize(tmp_path / "vault")
    home = tmp_path / "home"
    workspace = tmp_path / "work-without-almanac"
    write_codex_transcript(home, workspace)
    write_claude_transcript(home, workspace)

    first = app.collect.collect(
        CollectAgentRecords(
            providers=(AgentProvider.CODEX, AgentProvider.CLAUDE),
            home=home,
            include_content=True,
        )
    )
    second = app.collect.collect(
        CollectAgentRecords(
            providers=(AgentProvider.CODEX, AgentProvider.CLAUDE),
            home=home,
            include_content=True,
        )
    )

    assert first.sessions_discovered == 2
    assert first.events_added == 4
    assert second.events_added == 0
    sessions = app.sessions.list()
    assert len(sessions) == 2
    assert {session.cwd for session in sessions} == {workspace}
    assert all(session.content_captured for session in sessions)
    pages = tuple((vault / "inbox/agent-sessions").glob("*.md"))
    assert len(pages) == 2
    rendered = "\n".join(path.read_text(encoding="utf-8") for path in pages)
    assert "Keep agent decisions" in rendered
    assert "Claude remembers the outcome" in rendered


def test_collection_skips_awm_internal_workspaces(tmp_path: Path):
    app = isolated_app(tmp_path)
    app.vault.initialize(tmp_path / "vault")
    home = tmp_path / "home"
    write_codex_transcript(
        home,
        tmp_path / "state" / "distill-workspaces" / "distill-test" / "vault",
    )

    receipt = app.collect.collect(
        CollectAgentRecords(
            providers=(AgentProvider.CODEX,),
            home=home,
            include_content=True,
        )
    )

    assert receipt.sessions_discovered == 0
    assert receipt.session_ids == ()
    assert app.sessions.list() == ()


def test_metadata_collection_can_later_import_content(tmp_path: Path):
    app = isolated_app(tmp_path)
    vault = app.vault.initialize(tmp_path / "vault")
    home = tmp_path / "home"
    write_codex_transcript(home, tmp_path / "anywhere")
    request = CollectAgentRecords(
        providers=(AgentProvider.CODEX,),
        home=home,
        include_content=False,
    )

    metadata = app.collect.collect(request)
    session = app.sessions.get(metadata.session_ids[0])
    page = next((vault / "inbox/agent-sessions").glob("*.md"))

    assert not session.content_captured
    assert app.sessions.events(session.session_id) == ()
    assert "Transcript content has not been imported" in page.read_text(
        encoding="utf-8"
    )

    content = app.collect.collect(request.model_copy(update={"include_content": True}))

    assert content.events_added == 2
    assert app.sessions.get(session.session_id).content_captured


def test_appended_transcript_lines_advance_per_source_cursor(tmp_path: Path):
    app = isolated_app(tmp_path)
    app.vault.initialize(tmp_path / "vault")
    home = tmp_path / "home"
    transcript = write_codex_transcript(home, tmp_path / "workspace")
    request = CollectAgentRecords(
        providers=(AgentProvider.CODEX,),
        home=home,
        include_content=True,
    )

    first = app.collect.collect(request)
    with transcript.open("a", encoding="utf-8") as file:
        file.write(
            json.dumps(
                {
                    "timestamp": "2026-07-27T04:00:00Z",
                    "payload": {"message": "Record the final result."},
                }
            )
            + "\n"
        )
    second = app.collect.collect(request)

    assert first.events_added == 2
    assert second.events_added == 1
    events = app.sessions.events(first.session_ids[0])
    assert [event.source_line for event in events] == [2, 3, 4]


def test_imports_open_provider_record_bundle_into_wiki(tmp_path: Path):
    app = isolated_app(tmp_path)
    vault = app.vault.initialize(tmp_path / "vault")
    bundle = tmp_path / "local-agent.json"
    bundle.write_text(
        json.dumps(
            {
                "provider": "ollama.qwen",
                "session_id": "local-42",
                "title": "Local model architecture review",
                "cwd": str(tmp_path / "project"),
                "events": [
                    {
                        "kind": "message",
                        "role": "user",
                        "content": "Review the collector boundary.",
                    },
                    {
                        "kind": "message",
                        "role": "assistant",
                        "content": "Keep provider shapes at the edge.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    first = app.import_records.import_file(bundle)
    second = app.import_records.import_file(bundle)
    session = app.sessions.get(first.session_id)

    assert first.events_added == 2
    assert second.events_added == 0
    assert session.provider == "ollama.qwen"
    assert "Keep provider shapes" in first.wiki_path.read_text(encoding="utf-8")
    assert first.wiki_path.is_relative_to(vault)


def test_awm_cli_initializes_and_records_note(tmp_path: Path, capsys):
    state = tmp_path / "state"
    vault = tmp_path / "vault"

    assert main(("--state-dir", str(state), "init", str(vault))) == 0
    assert (
        main(
            (
                "--state-dir",
                str(state),
                "note",
                "CLI notes are retained.",
                "--title",
                "CLI note",
            )
        )
        == 0
    )
    assert main(("--state-dir", str(state), "search", "retained")) == 0

    output = capsys.readouterr().out
    assert "Initialized Agent Work Memory Vault" in output
    assert "Saved ses_" in output
    assert "CLI note" in output


def isolated_app(tmp_path: Path):
    return create_app(
        AgentWorkMemoryConfig(
            state_dir=tmp_path / "state",
            vault_path=None,
        )
    )


def write_codex_transcript(home: Path, workspace: Path) -> Path:
    transcript = home / ".codex/sessions/2026/07/27/codex.jsonl"
    transcript.parent.mkdir(parents=True)
    lines = (
        {
            "timestamp": "2026-07-27T01:00:00Z",
            "payload": {
                "id": "codex-session-1",
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
                    "content": [{"type": "input_text", "text": "Keep agent decisions"}],
                }
            },
        },
        {
            "timestamp": "2026-07-27T01:02:00Z",
            "payload": {
                "item": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Stored in the Wiki"}],
                }
            },
        },
    )
    transcript.write_text(
        "".join(json.dumps(line) + "\n" for line in lines),
        encoding="utf-8",
    )
    return transcript


def write_claude_transcript(home: Path, workspace: Path) -> Path:
    transcript = home / ".claude/projects/example/claude.jsonl"
    transcript.parent.mkdir(parents=True)
    lines = (
        {
            "type": "user",
            "timestamp": "2026-07-27T02:00:00Z",
            "sessionId": "claude-session-1",
            "cwd": str(workspace),
            "message": {
                "role": "user",
                "content": "What was the outcome?",
            },
        },
        {
            "type": "assistant",
            "timestamp": "2026-07-27T02:01:00Z",
            "sessionId": "claude-session-1",
            "cwd": str(workspace),
            "message": {
                "role": "assistant",
                "content": "Claude remembers the outcome.",
            },
        },
    )
    transcript.write_text(
        "".join(json.dumps(line) + "\n" for line in lines),
        encoding="utf-8",
    )
    return transcript


def test_public_package_surface_is_awm_only():
    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert pyproject["project"]["name"] == "agent-work-memory"
    assert pyproject["project"]["scripts"] == {
        "awm": "agentworkmemory.cli:main",
        "agent-work-memory": "agentworkmemory.cli:main",
    }
    assert pyproject["tool"]["setuptools"]["packages"]["find"]["include"] == [
        "agentworkmemory*"
    ]
