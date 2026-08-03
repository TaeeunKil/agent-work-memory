from datetime import datetime
from pathlib import Path

from pydantic import field_serializer

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.activity.models import ActivityTask
from agentworkmemory.services.sessions.models import AgentEventKind, SessionState
from agentworkmemory.services.translations.models import Locale, TranslationStatus


class ViewerOverview(AgentWorkMemoryModel):
    session_count: int
    knowledge_count: int
    pending_distill_count: int
    last_sync_status: str | None
    last_sync_at: datetime | None


class ViewerSchedule(AgentWorkMemoryModel):
    task: ActivityTask
    task_name: str
    next_run_at: datetime


class ViewerSession(AgentWorkMemoryModel):
    session_id: str
    provider: str
    title: str
    state: SessionState
    modified_at: datetime
    content_captured: bool
    distilled_at: datetime | None
    event_count: int


class ViewerEvent(AgentWorkMemoryModel):
    sequence: int
    kind: AgentEventKind
    role: str | None
    label: str
    occurred_at: datetime | None
    content: str


class ViewerSessionDetail(AgentWorkMemoryModel):
    session: ViewerSession
    workspace: str | None
    events: tuple[ViewerEvent, ...]


class ViewerPage(AgentWorkMemoryModel):
    path: Path
    title: str
    short_title_ko: str | None
    short_title_en: str | None
    original_locale: Locale
    category: str
    tags: tuple[str, ...]
    source_session_ids: tuple[str, ...]
    backlink_count: int

    @field_serializer("path")
    def serialize_path(self, value: Path) -> str:
        return value.as_posix()


class ViewerPageDetail(AgentWorkMemoryModel):
    path: Path
    title: str
    category: str
    html: str
    requested_locale: Locale
    resolved_locale: Locale
    original_locale: Locale
    translation_status: TranslationStatus
    backlinks: tuple[ViewerPage, ...]

    @field_serializer("path")
    def serialize_path(self, value: Path) -> str:
        return value.as_posix()


class ViewerGraphNode(AgentWorkMemoryModel):
    id: str
    title: str
    label: str
    short_title_ko: str | None
    short_title_en: str | None
    original_locale: Locale
    category: str
    tags: tuple[str, ...]
    source_count: int
    incoming_count: int
    outgoing_count: int


class ViewerGraphEdge(AgentWorkMemoryModel):
    source: str
    target: str


class ViewerGraph(AgentWorkMemoryModel):
    nodes: tuple[ViewerGraphNode, ...]
    edges: tuple[ViewerGraphEdge, ...]


class ViewerProject(AgentWorkMemoryModel):
    path: Path
    title: str
    topic_count: int
    source_session_ids: tuple[str, ...]

    @field_serializer("path")
    def serialize_path(self, value: Path) -> str:
        return value.as_posix()


class ViewerProjectDetail(AgentWorkMemoryModel):
    page: ViewerPageDetail
    topics: tuple[ViewerPage, ...]
    sessions: tuple[ViewerSession, ...]
