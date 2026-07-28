from importlib.resources import files
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import Field

from workalmanac.app import WorkAlmanac
from workalmanac.core import WorkAlmanacModel
from workalmanac.services.curators.models import ContentAccess
from workalmanac.workflows.distill import DistillSessions
from workalmanac.workflows.sync import SyncAgentRecords

ASSET_TYPES = {
    "app.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}


class ViewerSyncRequest(WorkAlmanacModel):
    providers: tuple[str, ...] = ("codex", "claude")
    include_content: bool = False
    home: Path = Field(default_factory=Path.home)


class ViewerDistillRequest(WorkAlmanacModel):
    session_ids: tuple[str, ...] = Field(min_length=1)
    runtime: str
    model: str | None = None
    content_access: ContentAccess = ContentAccess.METADATA_ONLY


def create_viewer_app(workalmanac: WorkAlmanac) -> FastAPI:
    server = FastAPI(
        title="Work Almanac",
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
        return workalmanac.viewer.overview().model_dump(mode="json")

    @server.get("/api/sessions")
    def sessions(limit: int = Query(default=100, ge=1, le=500)) -> list[object]:
        return [
            session.model_dump(mode="json")
            for session in workalmanac.viewer.sessions(limit)
        ]

    @server.get("/api/sessions/{session_id}")
    def session(session_id: str) -> dict[str, object]:
        try:
            return workalmanac.viewer.session(session_id).model_dump(mode="json")
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Session not found") from error

    @server.get("/api/pages")
    def pages() -> list[object]:
        return [page.model_dump(mode="json") for page in workalmanac.viewer.pages()]

    @server.get("/api/page")
    def page(path: str = Query(min_length=1)) -> dict[str, object]:
        try:
            return workalmanac.viewer.page(path).model_dump(mode="json")
        except (KeyError, OSError, UnicodeError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Page not found") from error

    @server.get("/api/search")
    def search(
        q: str = Query(min_length=1, max_length=500),
        limit: int = Query(default=30, ge=1, le=100),
    ) -> list[object]:
        visible = tuple(
            result
            for result in workalmanac.search.find(q, min(limit * 3, 300))
            if viewer_search_result(result.kind, result.identity)
        )
        return [result.model_dump(mode="json") for result in visible[:limit]]

    @server.get("/api/receipts")
    def receipts() -> dict[str, object]:
        return {
            "sync": [
                receipt.model_dump(mode="json")
                for receipt in workalmanac.synchronization.list(30)
            ],
            "distill": [
                receipt.model_dump(mode="json")
                for receipt in workalmanac.distillation.list(30)
            ],
        }

    @server.get("/api/activity")
    def activity() -> list[object]:
        return [
            run.model_dump(mode="json")
            for run in workalmanac.activity.list()
        ]

    @server.get("/api/schedules")
    def schedules() -> list[object]:
        return [
            schedule.model_dump(mode="json")
            for schedule in workalmanac.viewer.schedules()
        ]

    @server.get("/api/runtimes")
    def runtimes() -> list[object]:
        return [
            readiness.model_dump(mode="json")
            for readiness in workalmanac.curators.readiness()
        ]

    @server.post("/api/sync")
    def sync(
        request: ViewerSyncRequest,
        x_work_almanac_action: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_local_action(x_work_almanac_action)
        receipt = workalmanac.sync.run(
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
        x_work_almanac_action: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_local_action(x_work_almanac_action)
        receipt = workalmanac.distill.run(
            DistillSessions(
                session_ids=request.session_ids,
                runtime=request.runtime,
                model=request.model,
                content_access=request.content_access,
            )
        )
        return receipt.model_dump(mode="json")

    return server


def require_local_action(value: str | None) -> None:
    if value != "viewer":
        raise HTTPException(status_code=403, detail="Local action header required")


def asset_text(name: str) -> str:
    resource = files("workalmanac.viewer.assets").joinpath(name)
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
