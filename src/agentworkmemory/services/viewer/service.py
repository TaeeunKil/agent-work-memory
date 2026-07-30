import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from markdown_it import MarkdownIt

from agentworkmemory.services.activity.models import ActivityTask
from agentworkmemory.services.auto_distillation.service import AutoDistillationService
from agentworkmemory.services.automation.service import AutomationService
from agentworkmemory.services.sessions.models import AgentSession
from agentworkmemory.services.sessions.service import SessionsService
from agentworkmemory.services.synchronization.service import SynchronizationService
from agentworkmemory.services.vault.service import CATALOG_DIRECTORIES, VaultService
from agentworkmemory.services.viewer.models import (
    ViewerEvent,
    ViewerOverview,
    ViewerPage,
    ViewerPageDetail,
    ViewerProject,
    ViewerProjectDetail,
    ViewerSchedule,
    ViewerSession,
    ViewerSessionDetail,
)
from agentworkmemory.services.wiki.models import WikiPage
from agentworkmemory.services.wiki.service import (
    WIKILINK,
    WikiCatalogService,
    split_frontmatter,
    wiki_backlinks,
)

MARKDOWN = MarkdownIt("commonmark", {"html": False})
ALLOWED_TOP_LEVEL = frozenset({"Home.md", "README.md"})
SESSION_PREFIX = ("inbox", "agent-sessions")


class ViewerService:
    def __init__(
        self,
        sessions: SessionsService,
        vault: VaultService,
        wiki: WikiCatalogService,
        synchronization: SynchronizationService,
        automation: AutomationService,
        auto_distillation: AutoDistillationService,
    ):
        self.sessions_service = sessions
        self.vault = vault
        self.wiki = wiki
        self.synchronization = synchronization
        self.automation = automation
        self.auto_distillation = auto_distillation

    def overview(self) -> ViewerOverview:
        sessions = self.sessions_service.list()
        pages = self.wiki.pages()
        last_sync = self.synchronization.latest()
        return ViewerOverview(
            session_count=len(sessions),
            knowledge_count=len(pages),
            pending_distill_count=sum(
                1 for _ in self.sessions_service.distillation_candidates()
            ),
            last_sync_status=last_sync.status.value if last_sync is not None else None,
            last_sync_at=last_sync.finished_at if last_sync is not None else None,
        )

    def sessions(self, limit: int = 100) -> tuple[ViewerSession, ...]:
        return tuple(
            self.session_summary(session)
            for session in self.sessions_service.list()[:limit]
        )

    def schedules(self) -> tuple[ViewerSchedule, ...]:
        sync = self.automation.status()
        distill = self.auto_distillation.status()
        schedules = (
            viewer_schedule(
                ActivityTask.SYNC,
                sync.task_name,
                sync.next_run_at,
            ),
            viewer_schedule(
                ActivityTask.AUTO_DISTILL,
                distill.task_name,
                distill.next_run_at,
            ),
        )
        return tuple(
            sorted(
                (schedule for schedule in schedules if schedule is not None),
                key=lambda schedule: schedule.next_run_at,
            )
        )

    def session(self, session_id: str) -> ViewerSessionDetail:
        session = self.sessions_service.get(session_id)
        events = self.sessions_service.events(session_id)
        return ViewerSessionDetail(
            session=self.session_summary(session, len(events)),
            workspace=str(session.cwd) if session.cwd is not None else None,
            events=tuple(
                ViewerEvent(
                    sequence=event.sequence,
                    kind=event.kind,
                    role=event.role,
                    label=event.label,
                    occurred_at=event.occurred_at,
                    content=event.content,
                )
                for event in events
            ),
        )

    def pages(self) -> tuple[ViewerPage, ...]:
        pages = self.wiki.pages()
        backlinks = wiki_backlinks(pages)
        return tuple(
            viewer_page(page, len(backlinks.get(page.path, ()))) for page in pages
        )

    def page(self, value: str) -> ViewerPageDetail:
        relative = safe_viewer_page_path(value)
        root = self.vault.require_path()
        target = (root / relative).resolve()
        target.relative_to(root.resolve())
        if target.is_symlink() or not target.is_file():
            raise KeyError(f"unknown Wiki page: {relative}")
        raw = target.read_text(encoding="utf-8")
        _, body = split_frontmatter(raw)
        pages = self.wiki.pages()
        known = {page.path: page for page in pages}
        page = known.get(relative)
        title = page.title if page is not None else markdown_title(relative, body)
        category = page.category if page is not None else page_category(relative)
        backlinks = wiki_backlinks(pages).get(relative, ())
        return ViewerPageDetail(
            path=relative,
            title=title,
            category=category,
            html=render_markdown(body),
            backlinks=tuple(viewer_page(item, 0) for item in backlinks),
        )

    def projects(self) -> tuple[ViewerProject, ...]:
        pages = self.wiki.pages()
        backlinks = wiki_backlinks(pages)
        projects: list[ViewerProject] = []
        for project in sorted(
            (page for page in pages if page.category == "projects"),
            key=lambda page: page.title.casefold(),
        ):
            topics = project_topics(project, pages, backlinks)
            projects.append(
                ViewerProject(
                    path=project.path,
                    title=project.title,
                    topic_count=len(topics),
                    source_session_ids=project_source_session_ids(
                        project,
                        topics,
                    ),
                )
            )
        return tuple(projects)

    def project(self, value: str) -> ViewerProjectDetail:
        relative = safe_viewer_page_path(value)
        pages = self.wiki.pages()
        project = next(
            (
                page
                for page in pages
                if page.path == relative and page.category == "projects"
            ),
            None,
        )
        if project is None:
            raise KeyError(f"unknown project page: {relative}")
        topics = project_topics(project, pages, wiki_backlinks(pages))
        source_ids = project_source_session_ids(project, topics)
        sessions_by_id = {
            session.session_id: session for session in self.sessions_service.list()
        }
        sessions = tuple(
            self.session_summary(sessions_by_id[session_id])
            for session_id in source_ids
            if session_id in sessions_by_id
        )
        return ViewerProjectDetail(
            page=self.page(relative.as_posix()),
            topics=tuple(viewer_page(topic, 0) for topic in topics),
            sessions=sessions,
        )

    def session_summary(
        self,
        session: AgentSession,
        event_count: int | None = None,
    ) -> ViewerSession:
        count = (
            len(self.sessions_service.events(session.session_id))
            if event_count is None
            else event_count
        )
        return ViewerSession(
            session_id=session.session_id,
            provider=session.provider,
            title=session.title,
            state=session.state,
            modified_at=session.modified_at,
            content_captured=session.content_captured,
            distilled_at=session.distilled_at,
            event_count=count,
        )


def safe_viewer_page_path(value: str) -> Path:
    normalized = value.strip().replace("\\", "/").lstrip("/")
    relative = Path(normalized)
    if (
        not normalized
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.suffix.lower() != ".md"
    ):
        raise ValueError("invalid Wiki page path")
    if relative.as_posix() in ALLOWED_TOP_LEVEL:
        return relative
    if relative.parts[:2] == SESSION_PREFIX and len(relative.parts) == 3:
        return relative
    if relative.parts and relative.parts[0] in CATALOG_DIRECTORIES:
        return relative
    raise ValueError("Wiki page is outside the viewer scope")


def render_markdown(value: str) -> str:
    converted = WIKILINK.sub(render_wikilink, value)
    return MARKDOWN.render(converted)


def render_wikilink(match: re.Match[str]) -> str:
    raw = match.group(0)
    target = match.group(1).strip()
    alias = target
    if "|" in raw:
        alias = raw.rsplit("|", 1)[1].removesuffix("]]").strip()
    path = target if target.lower().endswith(".md") else f"{target}.md"
    safe_text = alias.replace("[", " ").replace("]", " ")
    return f"[{safe_text}](#/wiki/{quote(path, safe='')})"


def viewer_page(page: WikiPage, backlink_count: int) -> ViewerPage:
    return ViewerPage(
        path=page.path,
        title=page.title,
        category=page.category,
        tags=page.tags,
        source_session_ids=page.source_session_ids,
        backlink_count=backlink_count,
    )


def markdown_title(path: Path, body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# ") and line[2:].strip():
            return line[2:].strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


def page_category(path: Path) -> str:
    if path.parts[:2] == SESSION_PREFIX:
        return "agent-sessions"
    if len(path.parts) >= 2:
        return path.parts[0]
    return "home"


def viewer_schedule(
    task: ActivityTask,
    task_name: str,
    next_run_at: datetime | None,
) -> ViewerSchedule | None:
    if next_run_at is None:
        return None
    return ViewerSchedule(
        task=task,
        task_name=task_name,
        next_run_at=next_run_at,
    )


def project_topics(
    project: WikiPage,
    pages: tuple[WikiPage, ...],
    backlinks: dict[Path, tuple[WikiPage, ...]],
) -> tuple[WikiPage, ...]:
    by_path = {page.path: page for page in pages}
    related = {
        page.path: page
        for page in backlinks.get(project.path, ())
        if page.path != project.path
    }
    for outgoing in project.outgoing_links:
        page = by_path.get(outgoing)
        if page is not None and page.path != project.path:
            related[page.path] = page
    return tuple(sorted(related.values(), key=lambda page: page.title.casefold()))


def project_source_session_ids(
    project: WikiPage,
    topics: tuple[WikiPage, ...],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            session_id
            for page in (project, *topics)
            for session_id in page.source_session_ids
        )
    )
