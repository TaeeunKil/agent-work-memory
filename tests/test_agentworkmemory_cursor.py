import json
import sqlite3
from pathlib import Path

from agentworkmemory.app import create_app
from agentworkmemory.integrations.transcripts import CursorTranscriptCollector
from agentworkmemory.services.sessions.models import AgentProvider
from agentworkmemory.settings import AgentWorkMemoryConfig
from agentworkmemory.workflows.collect import CollectAgentRecords


def test_cursor_composer_enters_the_session_and_wiki_pipeline(tmp_path: Path):
    app = create_app(
        AgentWorkMemoryConfig(
            state_dir=tmp_path / "state",
            vault_path=None,
        )
    )
    vault = app.vault.initialize(tmp_path / "vault")
    home = tmp_path / "home"
    workspace = Path("C:/cursor-project")
    database = write_cursor_database(
        home,
        composer_id="cursor-session-1",
        name="Plan the Cursor collector",
        workspace_uri=workspace.as_uri(),
    )
    write_cursor_bubble(
        database,
        "cursor-session-1",
        "bubble-user",
        bubble_type=1,
        text="Keep Cursor decisions in the same Wiki.",
        created_at="2026-07-29T00:00:00Z",
    )
    write_cursor_bubble(
        database,
        "cursor-session-1",
        "bubble-assistant",
        bubble_type=2,
        text="The Cursor collector now owns Composer records.",
        created_at="2026-07-29T00:01:00Z",
    )
    write_cursor_bubble(
        database,
        "cursor-session-1",
        "bubble-tool",
        bubble_type=2,
        text="",
        created_at="2026-07-29T00:01:30Z",
    )
    request = CollectAgentRecords(
        providers=(AgentProvider.CURSOR,),
        home=home,
        include_content=True,
    )

    first = app.collect.collect(request)
    second = app.collect.collect(request)

    assert first.sessions_discovered == 1
    assert first.events_added == 2
    assert second.events_added == 0
    session = app.sessions.get(first.session_ids[0])
    assert session.title == "Plan the Cursor collector"
    assert session.cwd == workspace
    assert [event.role for event in app.sessions.events(session.session_id)] == [
        "user",
        "assistant",
    ]
    page = next((vault / "inbox" / "agent-sessions").glob("*.md"))
    rendered = page.read_text(encoding="utf-8")
    assert "Keep Cursor decisions" in rendered
    assert "Composer records" in rendered


def test_cursor_collection_adds_new_bubbles_incrementally(tmp_path: Path):
    app = create_app(
        AgentWorkMemoryConfig(
            state_dir=tmp_path / "state",
            vault_path=None,
        )
    )
    app.vault.initialize(tmp_path / "vault")
    home = tmp_path / "home"
    database = write_cursor_database(
        home,
        composer_id="cursor-session-2",
        name="Incremental Cursor chat",
        workspace_uri="file:///C:/cursor-incremental-workspace",
    )
    write_cursor_bubble(
        database,
        "cursor-session-2",
        "bubble-1",
        bubble_type=1,
        text="First message",
        created_at="2026-07-29T01:00:00Z",
    )
    request = CollectAgentRecords(
        providers=(AgentProvider.CURSOR,),
        home=home,
        include_content=True,
    )

    first = app.collect.collect(request)
    write_cursor_bubble(
        database,
        "cursor-session-2",
        "bubble-2",
        bubble_type=2,
        text="Later response",
        created_at="2026-07-29T01:01:00Z",
    )
    second = app.collect.collect(request)

    assert first.events_added == 1
    assert second.events_added == 1
    assert [
        event.content
        for event in app.sessions.events(first.session_ids[0])
    ] == ["First message", "Later response"]


def test_current_cursor_agent_transcript_enters_the_pipeline_incrementally(
    tmp_path: Path,
):
    app = create_app(
        AgentWorkMemoryConfig(
            state_dir=tmp_path / "state",
            vault_path=None,
        )
    )
    app.vault.initialize(tmp_path / "vault")
    home = tmp_path / "home"
    database = write_cursor_database(
        home,
        composer_id="current-cursor-session",
        name="Current Cursor transcript",
        workspace_uri="file:///C:/cursor-current-project",
    )
    transcript = write_cursor_agent_transcript(
        home,
        composer_id="current-cursor-session",
        project_slug="C-cursor-current-project",
    )
    write_cursor_agent_message(
        transcript,
        role="user",
        text=(
            "<user_query>\n"
            "Capture the current Cursor transcript format.\n"
            "</user_query>"
        ),
    )
    write_cursor_agent_message(
        transcript,
        role="assistant",
        text="Current Cursor Agent work now enters memory.\n\n[REDACTED]",
        tool_name="read_file",
    )
    write_cursor_agent_message(
        transcript,
        role="assistant",
        text="[REDACTED]",
    )
    request = CollectAgentRecords(
        providers=(AgentProvider.CURSOR,),
        home=home,
        include_content=True,
    )

    first = app.collect.collect(request)
    write_cursor_agent_message(
        transcript,
        role="assistant",
        text="A later response is collected incrementally.",
    )
    second = app.collect.collect(request)

    assert first.sessions_discovered == 1
    assert first.events_added == 2
    assert second.events_added == 1
    session = app.sessions.get(first.session_ids[0])
    assert session.source_path == database.resolve()
    assert session.title == "Current Cursor transcript"
    assert [
        (event.role, event.content)
        for event in app.sessions.events(session.session_id)
    ] == [
        ("user", "Capture the current Cursor transcript format."),
        ("assistant", "Current Cursor Agent work now enters memory."),
        ("assistant", "A later response is collected incrementally."),
    ]


def test_cursor_jsonl_uses_header_identity_and_metadata(tmp_path: Path):
    home = tmp_path / "home"
    workspace = Path("C:/cursor-jsonl-project")
    database = write_cursor_database(
        home,
        composer_id="jsonl-with-header",
        name="Current Cursor Agent",
        workspace_uri=workspace.as_uri(),
    )
    transcript = write_cursor_agent_transcript(
        home,
        composer_id="jsonl-with-header",
        project_slug="C-cursor-jsonl-project",
    )
    write_cursor_agent_message(
        transcript,
        role="user",
        text="Use the durable transcript body.",
    )

    sessions = CursorTranscriptCollector().discover(home)

    assert len(sessions) == 1
    assert sessions[0].source_path == database.resolve()
    assert sessions[0].content_path == transcript.resolve()
    assert sessions[0].title == "Current Cursor Agent"
    assert sessions[0].cwd == workspace


def test_cursor_prefers_existing_legacy_bubbles_and_excludes_empty_headers(
    tmp_path: Path,
):
    home = tmp_path / "home"
    database = write_cursor_database(
        home,
        composer_id="legacy-and-jsonl",
        name="Legacy conversation",
        workspace_uri="file:///C:/cursor-legacy-project",
    )
    write_cursor_header(
        database,
        composer_id="empty-header",
        name="",
        workspace_uri="file:///C:/cursor-empty-project",
    )
    write_cursor_bubble(
        database,
        "legacy-and-jsonl",
        "legacy-bubble",
        bubble_type=1,
        text="Keep the established source identity.",
        created_at="2026-07-29T01:00:00Z",
    )
    transcript = write_cursor_agent_transcript(
        home,
        composer_id="legacy-and-jsonl",
        project_slug="C-cursor-legacy-project",
    )
    write_cursor_agent_message(
        transcript,
        role="user",
        text="This duplicate source must not create another session.",
    )

    sessions = CursorTranscriptCollector().discover(home)

    assert [session.provider_session_id for session in sessions] == [
        "legacy-and-jsonl"
    ]
    assert sessions[0].source_path == database.resolve()
    assert sessions[0].content_path is None


def test_cursor_ignores_subagent_transcript_files(tmp_path: Path):
    home = tmp_path / "home"
    transcript = write_cursor_agent_transcript(
        home,
        composer_id="parent-agent",
        project_slug="C-cursor-subagents",
    )
    write_cursor_agent_message(
        transcript,
        role="user",
        text="Only the parent Agent is a retained session.",
    )
    subagent = transcript.parent / "subagents" / "child-agent.jsonl"
    subagent.parent.mkdir()
    write_cursor_agent_message(
        subagent,
        role="assistant",
        text="Do not create a separate child session.",
    )

    sessions = CursorTranscriptCollector().discover(home)

    assert [session.provider_session_id for session in sessions] == ["parent-agent"]


def test_cursor_workspace_uris_cover_local_wsl_and_ssh(tmp_path: Path):
    home = tmp_path / "home"
    database = write_cursor_database(
        home,
        composer_id="local",
        name="Local",
        workspace_uri="file:///C:/local-workspace",
    )
    write_cursor_header(
        database,
        composer_id="wsl",
        name="WSL",
        workspace_uri={
            "$mid": 1,
            "scheme": "vscode-remote",
            "authority": "wsl+Ubuntu",
            "path": "/home/user/wsl-project",
            "external": "vscode-remote://wsl+Ubuntu/home/user/wsl-project",
            "fsPath": "/home/user/wsl-project",
            "_sep": 1,
        },
    )
    write_cursor_header(
        database,
        composer_id="ssh",
        name="SSH",
        workspace_uri="vscode-remote://ssh-remote+ovion-dev-157/home/user/ssh-project",
    )
    for composer_id in ("local", "wsl", "ssh"):
        write_cursor_bubble(
            database,
            composer_id,
            f"bubble-{composer_id}",
            bubble_type=1,
            text=f"{composer_id} work",
            created_at="2026-07-29T00:00:00Z",
        )

    sessions = CursorTranscriptCollector().discover(home)
    by_id = {session.provider_session_id: session for session in sessions}

    assert by_id["local"].cwd == Path("C:/local-workspace")
    assert by_id["wsl"].cwd is not None
    assert by_id["wsl"].cwd.name == "wsl-project"
    assert "Ubuntu" in str(by_id["wsl"].cwd)
    assert by_id["ssh"].cwd is not None
    assert by_id["ssh"].cwd.name == "ssh-project"
    assert "ovion-dev-157" in str(by_id["ssh"].cwd)


def write_cursor_database(
    home: Path,
    *,
    composer_id: str,
    name: str,
    workspace_uri: str,
) -> Path:
    database = (
        home
        / "AppData"
        / "Roaming"
        / "Cursor"
        / "User"
        / "globalStorage"
        / "state.vscdb"
    )
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE composerHeaders (
              composerId TEXT PRIMARY KEY,
              lastUpdatedAt INTEGER NOT NULL,
              value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE cursorDiskKV (
              key TEXT PRIMARY KEY,
              value BLOB NOT NULL
            )
            """
        )
    write_cursor_header(
        database,
        composer_id=composer_id,
        name=name,
        workspace_uri=workspace_uri,
    )
    return database


def write_cursor_header(
    database: Path,
    *,
    composer_id: str,
    name: str,
    workspace_uri: object,
) -> None:
    payload = {
        "composerId": composer_id,
        "name": name,
        "createdAt": 1785283200000,
        "lastUpdatedAt": 1785283260000,
        "workspaceIdentifier": {
            "id": f"workspace-{composer_id}",
            "uri": workspace_uri,
        },
    }
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO composerHeaders (composerId, lastUpdatedAt, value)
            VALUES (?, ?, ?)
            """,
            (composer_id, payload["lastUpdatedAt"], json.dumps(payload)),
        )


def write_cursor_bubble(
    database: Path,
    composer_id: str,
    bubble_id: str,
    *,
    bubble_type: int,
    text: str,
    created_at: str,
) -> None:
    payload = {
        "_v": 3,
        "bubbleId": bubble_id,
        "type": bubble_type,
        "text": text,
        "createdAt": created_at,
    }
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
            (
                f"bubbleId:{composer_id}:{bubble_id}",
                json.dumps(payload).encode(),
            ),
        )


def write_cursor_agent_transcript(
    home: Path,
    *,
    composer_id: str,
    project_slug: str,
) -> Path:
    transcript = (
        home
        / ".cursor"
        / "projects"
        / project_slug
        / "agent-transcripts"
        / composer_id
        / f"{composer_id}.jsonl"
    )
    transcript.parent.mkdir(parents=True)
    transcript.touch()
    return transcript


def write_cursor_agent_message(
    transcript: Path,
    *,
    role: str,
    text: str,
    tool_name: str | None = None,
) -> None:
    content: list[dict[str, object]] = [{"type": "text", "text": text}]
    if tool_name is not None:
        content.append(
            {
                "type": "tool_use",
                "name": tool_name,
                "input": {"path": "README.md"},
            }
        )
    payload = {
        "role": role,
        "message": {"content": content},
    }
    with transcript.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload) + "\n")
