import threading
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from filelock import FileLock

from agentworkmemory.app import create_app
from agentworkmemory.cli import build_parser, dispatch
from agentworkmemory.services.activity import ActivityTask
from agentworkmemory.services.curators.models import (
    CuratorReadiness,
    CuratorRunRequest,
    CuratorRunResult,
    CuratorRunStatus,
)
from agentworkmemory.settings import AgentWorkMemoryConfig
from agentworkmemory.viewer.app import create_viewer_app


class ViewerCurator:
    runtime = "viewer-local"

    def check(self) -> CuratorReadiness:
        return CuratorReadiness(
            runtime=self.runtime,
            available=True,
            message="viewer curator ready",
        )

    def run(self, request: CuratorRunRequest) -> CuratorRunResult:
        (request.vault_path / "decisions" / "viewer-action.md").write_text(
            "# Viewer action\n\nThe viewer can trigger selected distillation.\n",
            encoding="utf-8",
        )
        return CuratorRunResult(
            runtime=self.runtime,
            status=CuratorRunStatus.SUCCEEDED,
            output_text="viewer action complete",
        )


def test_viewer_serves_private_overview_and_session_detail(tmp_path: Path):
    app, session = viewer_fixture(tmp_path)
    client = TestClient(create_viewer_app(app))

    root = client.get("/")
    overview = client.get("/api/overview")
    detail = client.get(f"/api/sessions/{session.session_id}")

    assert root.status_code == 200
    assert "Agent Work Memory" in root.text
    assert "frame-ancestors 'none'" in root.headers["content-security-policy"]
    assert root.headers["cache-control"] == "no-store"
    assert overview.json()["session_count"] == 1
    assert overview.json()["pending_distill_count"] == 1
    payload = detail.json()
    assert payload["session"]["title"] == "Viewer evidence"
    assert payload["events"][0]["content"] == "Evidence stays local."
    assert "source_path" not in detail.text


def test_viewer_renders_safe_markdown_and_bounded_wiki_paths(tmp_path: Path):
    app, _ = viewer_fixture(tmp_path)
    vault = app.vault.require_path()
    (vault / "decisions" / "safe-page.md").write_text(
        """# Safe page

<script>alert("no")</script>

See [[systems/context|System context]].
""",
        encoding="utf-8",
    )
    app.wiki.refresh()
    client = TestClient(create_viewer_app(app))

    page = client.get("/api/page", params={"path": "decisions/safe-page.md"})
    escaped = client.get("/api/page", params={"path": "../outside.md"})

    assert page.status_code == 200
    html = page.json()["html"]
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "#/wiki/systems%2Fcontext.md" in html
    assert escaped.status_code == 404


def test_viewer_search_hides_generated_and_duplicate_session_pages(tmp_path: Path):
    app, _ = viewer_fixture(tmp_path)
    client = TestClient(create_viewer_app(app))

    results = client.get("/api/search", params={"q": "Evidence"}).json()

    assert any(result["kind"] == "session" for result in results)
    assert not any(result["identity"].startswith("inbox/") for result in results)
    assert not any(result["identity"] == "Home.md" for result in results)


def test_viewer_aggregates_topics_and_evidence_under_project_hubs(
    tmp_path: Path,
):
    app, session = viewer_fixture(tmp_path)
    vault = app.vault.require_path()
    source = f"""sources:
  - session_id: {session.session_id}
    provider: manual
"""
    (vault / "projects" / "agent-work-memory.md").write_text(
        f"""---
{source}---
# Agent Work Memory

Topics: [[decisions/topic-pages]].
""",
        encoding="utf-8",
    )
    (vault / "decisions" / "topic-pages.md").write_text(
        f"""---
{source}---
# Topic pages

Project: [[projects/agent-work-memory]].
""",
        encoding="utf-8",
    )
    app.wiki.refresh()
    client = TestClient(create_viewer_app(app))

    projects = client.get("/api/projects")
    detail = client.get(
        "/api/project",
        params={"path": "projects/agent-work-memory.md"},
    )

    assert projects.status_code == 200
    project = projects.json()[0]
    assert Path(project["path"]) == Path("projects/agent-work-memory.md")
    assert project["title"] == "Agent Work Memory"
    assert project["topic_count"] == 1
    assert project["source_session_ids"] == [session.session_id]
    assert detail.status_code == 200
    assert Path(detail.json()["topics"][0]["path"]) == Path(
        "decisions/topic-pages.md"
    )
    assert detail.json()["sessions"][0]["session_id"] == session.session_id


def test_viewer_reports_schedules_in_next_run_order(
    tmp_path: Path,
    monkeypatch,
):
    app, _ = viewer_fixture(tmp_path)
    sync_at = datetime(2026, 7, 28, 7, 30, tzinfo=UTC)
    distill_at = datetime(2026, 7, 28, 7, 10, tzinfo=UTC)
    monkeypatch.setattr(app.automation.adapter, "available", lambda: True)
    monkeypatch.setattr(app.automation.adapter, "installed", lambda: True)
    monkeypatch.setattr(
        app.automation.adapter,
        "next_run_at",
        lambda: sync_at,
    )
    monkeypatch.setattr(
        app.auto_distillation.adapter,
        "available",
        lambda: True,
    )
    monkeypatch.setattr(
        app.auto_distillation.adapter,
        "installed",
        lambda: True,
    )
    monkeypatch.setattr(
        app.auto_distillation.adapter,
        "next_run_at",
        lambda: distill_at,
    )
    client = TestClient(create_viewer_app(app))

    schedules = client.get("/api/schedules").json()

    assert [schedule["task"] for schedule in schedules] == [
        "auto-distill",
        "sync",
    ]
    assert schedules[0]["next_run_at"] == "2026-07-28T07:10:00Z"


def test_viewer_mutations_require_header_and_record_receipts(tmp_path: Path):
    app, session = viewer_fixture(tmp_path)
    client = TestClient(create_viewer_app(app))
    request = {
        "providers": ["codex"],
        "include_content": False,
        "home": str(tmp_path / "empty-home"),
    }

    forbidden = client.post("/api/sync", json=request)
    synced = client.post(
        "/api/sync",
        json=request,
        headers={"X-AWM-Action": "viewer"},
    )
    distilled = client.post(
        "/api/distill",
        json={
            "session_ids": [session.session_id],
            "runtime": "viewer-local",
            "content_access": "selected-local",
        },
        headers={"X-AWM-Action": "viewer"},
    )
    receipts = client.get("/api/receipts").json()

    assert forbidden.status_code == 403
    assert synced.status_code == 200
    assert synced.json()["status"] == "succeeded"
    assert distilled.status_code == 200
    assert distilled.json()["status"] == "succeeded"
    assert receipts["sync"][0]["run_id"] == synced.json()["run_id"]
    assert receipts["distill"][0]["run_id"] == distilled.json()["run_id"]


def test_viewer_can_distill_a_bounded_pending_batch(tmp_path: Path):
    app, session = viewer_fixture(tmp_path)
    client = TestClient(create_viewer_app(app))

    distilled = client.post(
        "/api/distill/pending",
        json={
            "limit": 10,
            "runtime": "viewer-local",
            "content_access": "selected-local",
        },
        headers={"X-AWM-Action": "viewer"},
    )

    assert distilled.status_code == 200
    assert distilled.json()["session_ids"] == [session.session_id]
    assert app.sessions.get(session.session_id).distilled_at is not None
    activity = client.get("/api/activity").json()[0]
    assert activity["task"] == "auto-distill"
    assert activity["status"] == "succeeded"
    assert activity["summary"].startswith("Wiki build completed")


def test_pending_viewer_batch_stays_with_one_workspace_and_can_be_requeued(
    tmp_path: Path,
):
    app, initial = viewer_fixture(tmp_path)
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    first_a = app.sessions.add_manual_note("First A", cwd=project_a)
    second_a = app.sessions.add_manual_note("Second A", cwd=project_a)
    latest_b = app.sessions.add_manual_note("Latest B", cwd=project_b)
    app.sessions.mark_distilled(
        (initial.session_id,),
        runtime="viewer-local",
        distilled_at=datetime.now(UTC),
    )

    batch = app.sessions.pending_distillation(20)

    assert batch == (latest_b,)
    app.sessions.mark_distilled(
        (second_a.session_id,),
        runtime="viewer-local",
        distilled_at=datetime.now(UTC),
    )
    assert second_a.session_id not in {
        session.session_id for session in app.sessions.distillation_candidates()
    }

    app.sessions.requeue_distillation((second_a.session_id,))

    assert second_a.session_id in {
        session.session_id for session in app.sessions.distillation_candidates()
    }
    assert first_a.session_id in {
        session.session_id for session in app.sessions.distillation_candidates()
    }


def test_viewer_wiki_build_survives_unavailable_activity_ledger(
    tmp_path: Path,
    monkeypatch,
):
    app, session = viewer_fixture(tmp_path)

    def fail_activity(*_args, **_kwargs):
        raise OSError("activity ledger unavailable")

    monkeypatch.setattr(app.activity, "begin", fail_activity)
    client = TestClient(create_viewer_app(app))

    distilled = client.post(
        "/api/distill/pending",
        json={
            "limit": 1,
            "runtime": "viewer-local",
            "content_access": "selected-local",
        },
        headers={"X-AWM-Action": "viewer"},
    )

    assert distilled.status_code == 200
    assert distilled.json()["session_ids"] == [session.session_id]


def test_viewer_wiki_build_waits_for_active_synchronization(tmp_path: Path):
    app, _ = viewer_fixture(tmp_path)
    lock_acquired = threading.Event()
    release_lock = threading.Event()

    def hold_sync_lock() -> None:
        with FileLock(tmp_path / "state" / "sync.lock"):
            lock_acquired.set()
            release_lock.wait(timeout=0.2)

    holder = threading.Thread(target=hold_sync_lock)
    holder.start()
    assert lock_acquired.wait(timeout=1)
    client = TestClient(create_viewer_app(app))

    distilled = client.post(
        "/api/distill/pending",
        json={
            "limit": 1,
            "runtime": "viewer-local",
            "content_access": "selected-local",
        },
        headers={"X-AWM-Action": "viewer"},
    )
    holder.join(timeout=1)

    assert distilled.status_code == 200
    activity = client.get("/api/activity").json()[0]
    assert any(
        line.startswith("Synchronization is running")
        for line in activity["log_lines"]
    )
    assert any(
        line.startswith("Synchronization finished")
        for line in activity["log_lines"]
    )


def test_viewer_exposes_runtime_readiness_without_credentials(tmp_path: Path):
    app, _ = viewer_fixture(tmp_path)
    client = TestClient(create_viewer_app(app))

    runtimes = client.get("/api/runtimes")

    assert runtimes.status_code == 200
    assert runtimes.json() == [
        {
            "runtime": "viewer-local",
            "available": True,
            "message": "viewer curator ready",
            "repair": None,
        }
    ]


def test_viewer_exposes_clickable_scheduled_activity_data(tmp_path: Path):
    app, _ = viewer_fixture(tmp_path)
    run = app.activity.begin(
        ActivityTask.SYNC,
        process_id=1234,
    )
    app.activity.append_log(run, "Collecting SSH transcripts")
    client = TestClient(create_viewer_app(app))

    response = client.get("/api/activity")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["activity_id"] == run.activity_id
    assert payload[0]["status"] == "running"
    assert payload[0]["summary"] == "Collecting SSH transcripts"
    assert payload[0]["log_lines"] == ["Collecting SSH transcripts"]
    assert "source_path" not in response.text


def test_serve_cli_uses_loopback_viewer_runner(tmp_path: Path, monkeypatch):
    app, _ = viewer_fixture(tmp_path)
    calls: list[tuple[int, bool]] = []

    def fake_serve(app_value, *, port: int, open_browser: bool) -> None:
        assert app_value is app
        calls.append((port, open_browser))

    monkeypatch.setattr("agentworkmemory.viewer.runner.serve_viewer", fake_serve)
    args = build_parser().parse_args(("serve", "--port", "4932", "--no-open"))

    assert dispatch(args, app) == 0
    assert calls == [(4932, False)]


def viewer_fixture(tmp_path: Path):
    curator = ViewerCurator()
    app = create_app(
        AgentWorkMemoryConfig(state_dir=tmp_path / "state", vault_path=None),
        curator_adapters=(curator,),
    )
    app.vault.initialize(tmp_path / "vault")
    session = app.sessions.add_manual_note(
        "Evidence stays local.",
        title="Viewer evidence",
    )
    app.vault.refresh_session(session, app.sessions.events(session.session_id))
    app.wiki.refresh()
    return app, session
