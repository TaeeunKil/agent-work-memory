import json
import subprocess
import zipfile
from pathlib import Path

import pytest

from agentworkmemory.app import create_app
from agentworkmemory.cli import build_parser, dispatch
from agentworkmemory.integrations.processes import WINDOWS_CREATE_NO_WINDOW
from agentworkmemory.integrations.remotes.process import OpenSshRunner
from agentworkmemory.integrations.remotes.ssh import SshRemoteSnapshotAdapter
from agentworkmemory.services.remotes import (
    RemoteAccessError,
    RemoteAccessErrorKind,
    RemoteHost,
    RemoteManifest,
    RemoteSnapshot,
)
from agentworkmemory.services.remotes.models import RemoteFileObservation
from agentworkmemory.services.sessions.models import AgentProvider
from agentworkmemory.services.synchronization.models import SyncStatus
from agentworkmemory.settings import AgentWorkMemoryConfig
from agentworkmemory.workflows.sync import SyncAgentRecords


class FakeRemoteAdapter:
    def snapshot(
        self,
        host: RemoteHost,
        previous: RemoteManifest,
        cache_root: Path,
    ) -> RemoteSnapshot:
        home = cache_root / "home"
        transcript = home / ".codex/sessions/2026/07/28/remote.jsonl"
        payload = codex_transcript()
        if not transcript.is_file():
            transcript.parent.mkdir(parents=True)
            transcript.write_bytes(payload)
        observation = RemoteFileObservation(
            path=".codex/sessions/2026/07/28/remote.jsonl",
            provider=AgentProvider.CODEX,
            size_bytes=len(payload),
            modified_ns=1_753_680_000_000_000_000,
        )
        downloaded = int(not previous.files)
        return RemoteSnapshot(
            local_home=home,
            manifest=RemoteManifest(files=(observation,)),
            files_downloaded=downloaded,
            bytes_downloaded=len(payload) if downloaded else 0,
        )


class FailingRemoteAdapter:
    def snapshot(
        self,
        host: RemoteHost,
        previous: RemoteManifest,
        cache_root: Path,
    ) -> RemoteSnapshot:
        raise RemoteAccessError(RemoteAccessErrorKind.UNAVAILABLE)


class FakeSshRunner:
    def __init__(self, *, unsafe_archive: bool = False):
        self.payload = codex_transcript()
        self.downloads = 0
        self.unsafe_archive = unsafe_archive

    def capture(
        self,
        target: str,
        remote_command: str,
        *,
        timeout_seconds: int,
    ) -> bytes:
        return json.dumps(
            {
                "files": [
                    {
                        "path": ".codex/sessions/2026/07/28/remote.jsonl",
                        "provider": "codex",
                        "size_bytes": len(self.payload),
                        "modified_ns": 1_753_680_000_000_000_000,
                    }
                ]
            }
        ).encode()

    def download(
        self,
        target: str,
        remote_command: str,
        destination: Path,
        *,
        timeout_seconds: int,
        max_bytes: int,
    ) -> None:
        self.downloads += 1
        member = (
            "../escape.jsonl"
            if self.unsafe_archive
            else ".codex/sessions/2026/07/28/remote.jsonl"
        )
        with zipfile.ZipFile(destination, "w") as archive:
            archive.writestr(member, self.payload)


def test_registered_remote_is_included_in_normal_incremental_sync(
    tmp_path: Path,
):
    app = remote_app(tmp_path, FakeRemoteAdapter())
    app.vault.initialize(tmp_path / "vault")
    app.remotes.register("agent-box", (AgentProvider.CODEX,))
    request = SyncAgentRecords(
        providers=(AgentProvider.CODEX,),
        home=tmp_path / "local-home",
        include_content=True,
    )

    first = app.sync.run(request)
    second = app.sync.run(request)

    assert first.status is SyncStatus.SUCCEEDED
    assert first.sessions_discovered == 1
    assert first.events_added == 2
    assert second.events_added == 0
    overview = app.remotes.list()[0]
    assert overview.status.files_observed == 1
    assert overview.status.error_type is None


def test_remote_failure_does_not_block_local_sync(tmp_path: Path):
    app = remote_app(tmp_path, FailingRemoteAdapter())
    app.vault.initialize(tmp_path / "vault")
    app.remotes.register("offline-box", (AgentProvider.CODEX,))
    home = tmp_path / "local-home"
    transcript = home / ".codex/sessions/2026/07/28/local.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_bytes(codex_transcript("local-session"))

    receipt = app.sync.run(
        SyncAgentRecords(
            providers=(AgentProvider.CODEX,),
            home=home,
            include_content=True,
        )
    )

    assert receipt.status is SyncStatus.SUCCEEDED
    assert receipt.events_added == 2
    assert app.remotes.list()[0].status.error_type == "unavailable"


def test_remote_sync_reports_each_host_and_failure(tmp_path: Path):
    app = remote_app(tmp_path, FailingRemoteAdapter())
    app.vault.initialize(tmp_path / "vault")
    app.remotes.register("offline-box", (AgentProvider.CODEX,))
    progress: list[str] = []

    app.sync.run(
        SyncAgentRecords(
            providers=(AgentProvider.CODEX,),
            home=tmp_path / "local-home",
            include_content=True,
        ),
        progress=progress.append,
    )

    assert "Scanning SSH remote 1/1: offline-box." in progress
    assert "SSH remote offline-box unavailable: unavailable." in progress


def test_remote_cli_add_list_status_and_remove(tmp_path: Path, capsys):
    app = remote_app(tmp_path, FakeRemoteAdapter())

    add = build_parser().parse_args(
        ("remote", "add", "agent-box", "--from", "codex")
    )
    assert dispatch(add, app) == 0
    assert dispatch(build_parser().parse_args(("remote", "list")), app) == 0
    status = build_parser().parse_args(("remote", "status", "agent-box"))
    assert dispatch(status, app) == 0
    remove = build_parser().parse_args(("remote", "remove", "agent-box"))
    assert dispatch(remove, app) == 0

    output = capsys.readouterr().out
    assert "Registered agent-box" in output
    assert "never" in output
    assert "Retained local records were kept" in output


def test_ssh_snapshot_is_incremental_and_rejects_unsafe_archive(tmp_path: Path):
    runner = FakeSshRunner()
    adapter = SshRemoteSnapshotAdapter(runner)
    host = RemoteHost(
        target="agent-box",
        providers=(AgentProvider.CODEX,),
        added_at="2026-07-28T00:00:00Z",
    )

    first = adapter.snapshot(host, RemoteManifest(), tmp_path / "safe")
    second = adapter.snapshot(host, first.manifest, tmp_path / "safe")

    assert first.files_downloaded == 1
    assert second.files_downloaded == 0
    assert runner.downloads == 1

    unsafe = SshRemoteSnapshotAdapter(FakeSshRunner(unsafe_archive=True))
    with pytest.raises(RemoteAccessError, match="unsafe"):
        unsafe.snapshot(host, RemoteManifest(), tmp_path / "unsafe")
    assert not (tmp_path / "escape.jsonl").exists()


def test_windows_ssh_capture_process_is_hidden(
    monkeypatch: pytest.MonkeyPatch,
):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(
        "agentworkmemory.integrations.remotes.process.subprocess.run",
        fake_run,
    )

    output = OpenSshRunner("ssh.exe").capture(
        "agent-box",
        "printf ok",
        timeout_seconds=10,
    )

    assert output == b"ok"
    assert captured["creationflags"] == WINDOWS_CREATE_NO_WINDOW


def test_doctor_explains_that_captured_sessions_need_distillation(
    tmp_path: Path,
):
    app = remote_app(tmp_path, FakeRemoteAdapter())
    app.vault.initialize(tmp_path / "vault")
    app.remotes.register("agent-box", (AgentProvider.CODEX,))
    app.sync.run(
        SyncAgentRecords(
            providers=(AgentProvider.CODEX,),
            home=tmp_path / "local-home",
            include_content=True,
        )
    )

    checks = {check.name: check for check in app.diagnostics.run(tmp_path)}

    assert "no durable Wiki pages" in checks["knowledge"].message
    assert "awm distill" in checks["knowledge"].message


def remote_app(tmp_path: Path, adapter):
    return create_app(
        AgentWorkMemoryConfig(
            state_dir=tmp_path / "state",
            vault_path=None,
        ),
        remote_adapter=adapter,
    )


def codex_transcript(session_id: str = "remote-session") -> bytes:
    lines = (
        {
            "timestamp": "2026-07-28T01:00:00Z",
            "payload": {
                "id": session_id,
                "cwd": "/work/project",
                "thread_source": "user",
            },
        },
        {
            "timestamp": "2026-07-28T01:01:00Z",
            "payload": {
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Keep the remote decision"}
                    ],
                }
            },
        },
        {
            "timestamp": "2026-07-28T01:02:00Z",
            "payload": {
                "item": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": "Stored from SSH"}
                    ],
                }
            },
        },
    )
    return "".join(json.dumps(line) + "\n" for line in lines).encode()
