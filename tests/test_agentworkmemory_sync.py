import json
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from filelock import FileLock

from agentworkmemory.app import create_app
from agentworkmemory.cli import build_parser, dispatch
from agentworkmemory.integrations.automation.windows import (
    background_python_executable,
    scheduled_sync_action,
    scheduled_task_next_run,
    windows_executable_subsystem,
)
from agentworkmemory.services.automation.models import AutoSyncSettings
from agentworkmemory.services.sessions.models import (
    AgentEventKind,
    AgentProvider,
    SessionState,
)
from agentworkmemory.services.synchronization.models import SyncStatus
from agentworkmemory.settings import AgentWorkMemoryConfig
from agentworkmemory.workflows.sync import SyncAgentRecords


class FakeScheduler:
    task_name = "AgentWorkMemory Test Sync"

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

    def next_run_at(self) -> datetime | None:
        return None

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


def test_sync_reports_coarse_progress(tmp_path: Path):
    app = sync_app(tmp_path)
    app.vault.initialize(tmp_path / "vault")
    home = tmp_path / "home"
    write_codex_transcript(home, tmp_path / "project")
    progress: list[str] = []

    receipt = app.sync.run(
        SyncAgentRecords(
            providers=(AgentProvider.CODEX,),
            home=home,
            include_content=True,
        ),
        progress=progress.append,
    )

    assert receipt.status is SyncStatus.SUCCEEDED
    assert progress == [
        "Starting local transcript collection.",
        "Scanning codex transcripts.",
        "codex transcripts complete: 1 session(s), 2 new event(s).",
        "Starting registered SSH remote collection.",
        "Refreshing search index.",
        "Synchronization complete: 1 session(s), 2 new event(s).",
    ]


def test_sync_normalizes_modern_codex_records_and_omits_telemetry(tmp_path: Path):
    app = sync_app(tmp_path)
    app.vault.initialize(tmp_path / "vault")
    home = tmp_path / "home"
    write_modern_codex_transcript(home, tmp_path / "project")

    receipt = app.sync.run(
        SyncAgentRecords(
            providers=(AgentProvider.CODEX,),
            home=home,
            include_content=True,
        )
    )

    assert receipt.events_added == 6
    (session,) = app.sessions.list()
    events = app.sessions.events(session.session_id)
    assert tuple(event.kind for event in events) == (
        AgentEventKind.MESSAGE,
        AgentEventKind.MESSAGE,
        AgentEventKind.TOOL_CALL,
        AgentEventKind.TOOL_RESULT,
        AgentEventKind.TOOL_CALL,
        AgentEventKind.TOOL_RESULT,
    )
    assert [event.content for event in events].count("Keep this modern decision") == 1
    rendered = "\n".join(event.content for event in events)
    assert "encrypted-reasoning" not in rendered
    assert "token_count" not in rendered
    assert "turn_context" not in rendered
    assert '"cmd":"pytest"' in rendered
    assert "apply_patch" in rendered


def test_sync_replays_events_when_normalizer_version_changes(tmp_path: Path):
    app = sync_app(tmp_path)
    app.vault.initialize(tmp_path / "vault")
    home = tmp_path / "home"
    write_modern_codex_transcript(home, tmp_path / "project")
    request = SyncAgentRecords(
        providers=(AgentProvider.CODEX,),
        home=home,
        include_content=True,
    )
    app.sync.run(request)
    (session,) = app.sessions.list()
    with sqlite3.connect(app.sessions.store.database_path) as connection:
        connection.execute(
            "UPDATE collector_cursors SET normalizer_version = 'legacy'"
        )
        connection.execute(
            """
            INSERT INTO agent_events (
              event_id, session_id, sequence, kind, role, label,
              occurred_at, content, source_line, created_at
            ) VALUES (
              'evt_stale', ?, 999, 'raw', NULL, 'raw',
              NULL, 'stale transport envelope', 999, ?
            )
            """,
            (session.session_id, datetime.now(UTC).isoformat()),
        )
        connection.commit()

    replay = app.sync.run(request)

    assert replay.events_added == 6
    events = app.sessions.events(session.session_id)
    assert len(events) == 6
    assert all(event.event_id != "evt_stale" for event in events)


def test_sync_deduplicates_a_codex_message_across_incremental_reads(
    tmp_path: Path,
):
    app = sync_app(tmp_path)
    app.vault.initialize(tmp_path / "vault")
    home = tmp_path / "home"
    transcript = home / ".codex/sessions/2026/08/06/incremental.jsonl"
    transcript.parent.mkdir(parents=True)
    records = (
        {
            "type": "session_meta",
            "payload": {
                "id": "incremental-codex-session",
                "cwd": str(tmp_path / "project"),
                "thread_source": "user",
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "One decision"}],
            },
        },
    )
    transcript.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    request = SyncAgentRecords(
        providers=(AgentProvider.CODEX,),
        home=home,
        include_content=True,
    )
    first = app.sync.run(request)
    with transcript.open("a", encoding="utf-8") as file:
        file.write(
            json.dumps(
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "user_message",
                        "message": "One decision",
                    },
                }
            )
            + "\n"
        )

    second = app.sync.run(request)

    assert first.events_added == 1
    assert second.events_added == 0
    (session,) = app.sessions.list()
    assert [event.content for event in app.sessions.events(session.session_id)] == [
        "One decision"
    ]


def test_sync_tracks_codex_archive_move_as_the_same_completed_session(
    tmp_path: Path,
):
    app = sync_app(tmp_path)
    app.vault.initialize(tmp_path / "vault")
    home = tmp_path / "home"
    live = write_modern_codex_transcript(home, tmp_path / "project")
    request = SyncAgentRecords(
        providers=(AgentProvider.CODEX,),
        home=home,
        include_content=True,
    )
    app.sync.run(request)
    (before,) = app.sessions.list()
    archived = home / ".codex" / "archived_sessions" / live.name
    archived.parent.mkdir(parents=True)
    live.replace(archived)

    app.sync.run(request)

    (after,) = app.sessions.list()
    assert after.session_id == before.session_id
    assert after.source_path == archived.resolve()
    assert after.state is SessionState.COMPLETE
    assert after.ended_at == after.modified_at
    assert len(app.sessions.events(after.session_id)) == 6


def test_overlapping_sync_exits_without_collecting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    app = sync_app(tmp_path)
    app.vault.initialize(tmp_path / "vault")
    lock = FileLock(tmp_path / "state" / "sync.lock")

    def fail_begin(**_kwargs):
        raise AssertionError("overlapping sync must not touch the database")

    monkeypatch.setattr(app.synchronization, "begin", fail_begin)

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


def test_scheduled_action_uses_module_and_no_remote_distillation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "agentworkmemory.integrations.automation.windows.background_python_executable",
        lambda: r"C:\AWM Runtime\pythonw.exe",
    )
    settings = AutoSyncSettings(
        interval_minutes=5,
        providers=(AgentProvider.CODEX, AgentProvider.CLAUDE),
        home=tmp_path / "User Home",
        include_content=False,
    )

    action = scheduled_sync_action(settings, tmp_path / "State Dir")

    assert "pythonw.exe" in action
    assert "-m agentworkmemory.scheduled" in action
    assert "--from codex" in action
    assert "--from claude" in action
    assert "--include-content" not in action
    assert "distill" not in action


def test_background_python_prefers_current_gui_runtime(tmp_path: Path):
    current = tmp_path / "project" / "Scripts" / "python.exe"
    current.parent.mkdir(parents=True)
    write_windows_executable(current.with_name("pythonw.exe"), subsystem=2)
    tool = tmp_path / "tools" / "agent-work-memory" / "Scripts" / "pythonw.exe"
    write_windows_executable(tool, subsystem=2)

    selected = background_python_executable(
        executable=current,
        environment={"UV_TOOL_DIR": str(tmp_path / "tools")},
        platform="win32",
    )

    assert selected == str(current.with_name("pythonw.exe"))


def test_background_python_rejects_console_venv_and_uses_uv_tool(tmp_path: Path):
    current = tmp_path / "project" / "Scripts" / "python.exe"
    current.parent.mkdir(parents=True)
    write_windows_executable(current.with_name("pythonw.exe"), subsystem=3)
    tool = tmp_path / "tools" / "agent-work-memory" / "Scripts" / "pythonw.exe"
    write_windows_executable(tool, subsystem=2)

    selected = background_python_executable(
        executable=current,
        environment={"UV_TOOL_DIR": str(tmp_path / "tools")},
        platform="win32",
    )

    assert selected == str(tool)


def test_background_python_uses_default_app_data_tool_path(tmp_path: Path):
    current = tmp_path / "project" / "Scripts" / "python.exe"
    current.parent.mkdir(parents=True)
    write_windows_executable(current.with_name("pythonw.exe"), subsystem=3)
    tool = (
        tmp_path
        / "Roaming"
        / "uv"
        / "tools"
        / "agent-work-memory"
        / "Scripts"
        / "pythonw.exe"
    )
    write_windows_executable(tool, subsystem=2)

    selected = background_python_executable(
        executable=current,
        environment={"APPDATA": str(tmp_path / "Roaming")},
        platform="win32",
    )

    assert selected == str(tool)


def test_background_python_resolves_relative_uv_tool_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    current = tmp_path / "project" / "Scripts" / "python.exe"
    current.parent.mkdir(parents=True)
    write_windows_executable(current.with_name("pythonw.exe"), subsystem=3)
    tool = tmp_path / "tools" / "agent-work-memory" / "Scripts" / "pythonw.exe"
    write_windows_executable(tool, subsystem=2)

    selected = background_python_executable(
        executable=current,
        environment={"UV_TOOL_DIR": "tools"},
        platform="win32",
    )

    assert selected == str(tool)


def test_background_python_refuses_to_register_console_task(tmp_path: Path):
    current = tmp_path / "project" / "Scripts" / "python.exe"
    current.parent.mkdir(parents=True)
    write_windows_executable(current.with_name("pythonw.exe"), subsystem=3)

    with pytest.raises(RuntimeError, match="consoleless Windows Python"):
        background_python_executable(
            executable=current,
            environment={},
            platform="win32",
        )


def test_windows_executable_subsystem_rejects_non_pe_file(tmp_path: Path):
    executable = tmp_path / "pythonw.exe"
    executable.write_bytes(b"not a Windows executable")

    assert windows_executable_subsystem(executable) is None


def test_windows_scheduler_reads_structured_next_run(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "agentworkmemory.integrations.automation.windows.shutil.which",
        lambda _name: "powershell.exe",
    )
    monkeypatch.setattr(
        "agentworkmemory.integrations.automation.windows.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=(),
            returncode=0,
            stdout='{"next_run_at":"2026-07-28T06:20:00.0000000Z"}',
            stderr="",
        ),
    )

    assert scheduled_task_next_run("AWM Sync") == datetime(
        2026,
        7,
        28,
        6,
        20,
        tzinfo=UTC,
    )


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
        AgentWorkMemoryConfig(
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


def write_modern_codex_transcript(home: Path, workspace: Path) -> Path:
    transcript = home / ".codex/sessions/2026/08/06/modern.jsonl"
    transcript.parent.mkdir(parents=True)
    lines = (
        {
            "type": "session_meta",
            "timestamp": "2026-08-06T01:00:00Z",
            "payload": {
                "id": "modern-codex-session",
                "cwd": str(workspace),
                "thread_source": "user",
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-08-06T01:01:00Z",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Keep this modern decision"}
                ],
            },
        },
        {
            "type": "event_msg",
            "timestamp": "2026-08-06T01:01:00Z",
            "payload": {
                "type": "user_message",
                "message": "Keep this modern decision",
            },
        },
        {
            "type": "response_item",
            "timestamp": "2026-08-06T01:02:00Z",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": "Stored without telemetry"}
                ],
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "reasoning",
                "encrypted_content": "encrypted-reasoning",
                "summary": [],
            },
        },
        {
            "type": "event_msg",
            "payload": {"type": "token_count", "info": {"total": 9000}},
        },
        {
            "type": "turn_context",
            "payload": {"cwd": str(workspace), "summary": "turn_context"},
        },
        {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": "shell",
                "arguments": '{"cmd":"pytest"}',
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "output": "12 passed",
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call",
                "name": "apply_patch",
                "input": "apply_patch input",
            },
        },
        {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call_output",
                "output": "apply_patch complete",
            },
        },
    )
    transcript.write_text(
        "".join(json.dumps(line) + "\n" for line in lines),
        encoding="utf-8",
    )
    return transcript


def write_windows_executable(path: Path, *, subsystem: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pe_offset = 0x80
    optional_header = pe_offset + 4 + 20
    payload = bytearray(optional_header + 70)
    payload[:2] = b"MZ"
    payload[0x3C:0x40] = pe_offset.to_bytes(4, "little")
    payload[pe_offset : pe_offset + 4] = b"PE\0\0"
    payload[optional_header : optional_header + 2] = (0x20B).to_bytes(2, "little")
    payload[optional_header + 68 : optional_header + 70] = subsystem.to_bytes(
        2,
        "little",
    )
    path.write_bytes(payload)
