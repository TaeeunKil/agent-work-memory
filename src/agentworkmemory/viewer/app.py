import os
from contextlib import suppress
from importlib.resources import files
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import Field

from agentworkmemory.app import AgentWorkMemory
from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.activity import ActivityRun, ActivityTask
from agentworkmemory.services.curators.models import ContentAccess
from agentworkmemory.services.distillation.models import DistillReceipt
from agentworkmemory.services.distillation.outcomes import (
    summarize_session_outcomes,
)
from agentworkmemory.services.sessions.models import LOCAL_TRANSCRIPT_PROVIDERS
from agentworkmemory.workflows.distill import DistillSessions
from agentworkmemory.workflows.distill.coordination import (
    DistillationAlreadyRunning,
    SynchronizationWaitExpired,
)
from agentworkmemory.workflows.sync import SyncAgentRecords

ASSET_TYPES = {
    "app.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "cytoscape.min.js": "text/javascript; charset=utf-8",
}


class ViewerSyncRequest(AgentWorkMemoryModel):
    providers: tuple[str, ...] = LOCAL_TRANSCRIPT_PROVIDERS
    include_content: bool = False
    home: Path = Field(default_factory=Path.home)


class ViewerDistillRequest(AgentWorkMemoryModel):
    session_ids: tuple[str, ...] = Field(min_length=1)
    runtime: str
    model: str | None = None
    content_access: ContentAccess = ContentAccess.METADATA_ONLY


class ViewerPendingDistillRequest(AgentWorkMemoryModel):
    limit: int = Field(default=10, ge=1, le=20)
    runtime: str
    model: str | None = None
    content_access: ContentAccess = ContentAccess.METADATA_ONLY


def create_viewer_app(memory: AgentWorkMemory) -> FastAPI:
    server = FastAPI(
        title="Agent Work Memory",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    server.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "::1", "testserver"],
    )

    @server.middleware("http")
    async def private_response_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        )
        return response

    @server.get("/", response_class=HTMLResponse)
    def index() -> str:
        return asset_text("index.html")

    @server.get("/assets/{asset_name}")
    def asset(asset_name: str) -> Response:
        media_type = ASSET_TYPES.get(asset_name)
        if media_type is None:
            raise HTTPException(status_code=404)
        return Response(asset_text(asset_name), media_type=media_type)

    @server.get("/api/overview")
    def overview() -> dict[str, object]:
        return memory.viewer.overview().model_dump(mode="json")

    @server.get("/api/sessions")
    def sessions(limit: int = Query(default=100, ge=1, le=500)) -> list[object]:
        return [
            session.model_dump(mode="json")
            for session in memory.viewer.sessions(limit)
        ]

    @server.get("/api/sessions/{session_id}")
    def session(session_id: str) -> dict[str, object]:
        try:
            return memory.viewer.session(session_id).model_dump(mode="json")
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Session not found") from error

    @server.get("/api/pages")
    def pages() -> list[object]:
        return [page.model_dump(mode="json") for page in memory.viewer.pages()]

    @server.get("/api/graph")
    def graph() -> dict[str, object]:
        return memory.viewer.graph().model_dump(mode="json")

    @server.get("/api/projects")
    def projects() -> list[object]:
        return [
            project.model_dump(mode="json")
            for project in memory.viewer.projects()
        ]

    @server.get("/api/project")
    def project(path: str = Query(min_length=1)) -> dict[str, object]:
        try:
            return memory.viewer.project(path).model_dump(mode="json")
        except (KeyError, OSError, UnicodeError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Project not found") from error

    @server.get("/api/page")
    def page(path: str = Query(min_length=1)) -> dict[str, object]:
        try:
            return memory.viewer.page(path).model_dump(mode="json")
        except (KeyError, OSError, UnicodeError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Page not found") from error

    @server.get("/api/search")
    def search(
        q: str = Query(min_length=1, max_length=500),
        limit: int = Query(default=30, ge=1, le=100),
    ) -> list[object]:
        visible = tuple(
            result
            for result in memory.search.find(q, min(limit * 3, 300))
            if viewer_search_result(result.kind, result.identity)
        )
        return [result.model_dump(mode="json") for result in visible[:limit]]

    @server.get("/api/receipts")
    def receipts() -> dict[str, object]:
        return {
            "sync": [
                receipt.model_dump(mode="json")
                for receipt in memory.synchronization.list(30)
            ],
            "distill": [
                receipt.model_dump(mode="json")
                for receipt in memory.distillation.list(30)
            ],
        }

    @server.get("/api/activity")
    def activity() -> list[object]:
        return [
            run.model_dump(mode="json")
            for run in memory.activity.list()
        ]

    @server.get("/api/schedules")
    def schedules() -> list[object]:
        return [
            schedule.model_dump(mode="json")
            for schedule in memory.viewer.schedules()
        ]

    @server.get("/api/runtimes")
    def runtimes() -> list[object]:
        return [
            readiness.model_dump(mode="json")
            for readiness in memory.curators.readiness()
        ]

    @server.post("/api/sync")
    def sync(
        request: ViewerSyncRequest,
        x_awm_action: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_local_action(x_awm_action)
        receipt = memory.sync.run(
            SyncAgentRecords(
                providers=request.providers,
                home=request.home.expanduser().resolve(),
                include_content=request.include_content,
            )
        )
        return receipt.model_dump(mode="json")

    @server.post("/api/distill")
    def distill(
        request: ViewerDistillRequest,
        x_awm_action: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_local_action(x_awm_action)
        receipt = run_viewer_distill(
            memory,
            DistillSessions(
                session_ids=request.session_ids,
                runtime=request.runtime,
                model=request.model,
                content_access=request.content_access,
            )
        )
        return receipt.model_dump(mode="json")

    @server.post("/api/distill/pending")
    def distill_pending(
        request: ViewerPendingDistillRequest,
        x_awm_action: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_local_action(x_awm_action)
        pending = memory.sessions.pending_distillation(request.limit)
        if not pending:
            raise HTTPException(
                status_code=409,
                detail="No captured sessions are waiting to be distilled.",
            )
        receipt = run_viewer_distill(
            memory,
            DistillSessions(
                session_ids=tuple(session.session_id for session in pending),
                runtime=request.runtime,
                model=request.model,
                content_access=request.content_access,
            )
        )
        return receipt.model_dump(mode="json")

    return server


def run_viewer_distill(
    memory: AgentWorkMemory,
    request: DistillSessions,
) -> DistillReceipt:
    activity: ActivityRun | None = None
    with suppress(OSError):
        activity = memory.activity.begin(
            ActivityTask.AUTO_DISTILL,
            process_id=os.getpid(),
        )
        memory.activity.append_log(
            activity,
            f"Building Wiki from {len(request.session_ids)} selected session(s).",
        )

    def record_progress(message: str) -> None:
        if activity is not None:
            with suppress(OSError):
                memory.activity.append_log(activity, message)

    def finish_activity(exit_code: int) -> None:
        if activity is not None:
            with suppress(OSError):
                memory.activity.finish(activity, exit_code=exit_code)

    try:
        with (
            memory.distill_coordination.exclusive(),
            memory.distill_coordination.after_synchronization(record_progress),
        ):
            receipt = memory.distill.run(request)
    except DistillationAlreadyRunning as error:
        record_progress("Skipped because another Wiki distillation is running.")
        finish_activity(0)
        raise HTTPException(
            status_code=409,
            detail="Another Wiki distillation is already running.",
        ) from error
    except SynchronizationWaitExpired as error:
        record_progress("Skipped because synchronization exceeded the wait limit.")
        finish_activity(0)
        raise HTTPException(
            status_code=409,
            detail="Synchronization did not finish within 10 minutes.",
        ) from error
    except Exception as error:
        record_progress(f"Wiki build failed: {type(error).__name__}.")
        finish_activity(1)
        raise
    record_progress(
        "Wiki build completed; "
        f"{len(receipt.changed_files)} topic page(s) changed."
    )
    record_progress(
        f"Session outcomes: {summarize_session_outcomes(receipt.session_outcomes)}."
    )
    finish_activity(0)
    return receipt


def require_local_action(value: str | None) -> None:
    if value != "viewer":
        raise HTTPException(status_code=403, detail="Local action header required")


def asset_text(name: str) -> str:
    resource = files("agentworkmemory.viewer.assets").joinpath(name)
    if not resource.is_file():
        raise HTTPException(status_code=404)
    return resource.read_text(encoding="utf-8")


def viewer_search_result(kind: str, identity: str) -> bool:
    if kind != "wiki":
        return True
    path = identity.replace("\\", "/")
    return not (
        path in {"Home.md", "README.md"}
        or path.endswith("/_index.md")
        or path.startswith("inbox/agent-sessions/")
    )
