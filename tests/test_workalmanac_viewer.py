from pathlib import Path

from fastapi.testclient import TestClient

from workalmanac.app import create_app
from workalmanac.cli import build_parser, dispatch
from workalmanac.services.curators.models import (
    CuratorReadiness,
    CuratorRunRequest,
    CuratorRunResult,
    CuratorRunStatus,
)
from workalmanac.settings import WorkAlmanacConfig
from workalmanac.viewer.app import create_viewer_app


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
    assert "Work Almanac" in root.text
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
        headers={"X-Work-Almanac-Action": "viewer"},
    )
    distilled = client.post(
        "/api/distill",
        json={
            "session_ids": [session.session_id],
            "runtime": "viewer-local",
            "content_access": "selected-local",
        },
        headers={"X-Work-Almanac-Action": "viewer"},
    )
    receipts = client.get("/api/receipts").json()

    assert forbidden.status_code == 403
    assert synced.status_code == 200
    assert synced.json()["status"] == "succeeded"
    assert distilled.status_code == 200
    assert distilled.json()["status"] == "succeeded"
    assert receipts["sync"][0]["run_id"] == synced.json()["run_id"]
    assert receipts["distill"][0]["run_id"] == distilled.json()["run_id"]


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


def test_serve_cli_uses_loopback_viewer_runner(tmp_path: Path, monkeypatch):
    app, _ = viewer_fixture(tmp_path)
    calls: list[tuple[int, bool]] = []

    def fake_serve(app_value, *, port: int, open_browser: bool) -> None:
        assert app_value is app
        calls.append((port, open_browser))

    monkeypatch.setattr("workalmanac.viewer.runner.serve_viewer", fake_serve)
    args = build_parser().parse_args(("serve", "--port", "4932", "--no-open"))

    assert dispatch(args, app) == 0
    assert calls == [(4932, False)]


def viewer_fixture(tmp_path: Path):
    curator = ViewerCurator()
    app = create_app(
        WorkAlmanacConfig(state_dir=tmp_path / "state", vault_path=None),
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
