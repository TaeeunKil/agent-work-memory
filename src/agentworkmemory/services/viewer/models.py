from datetime import datetime
from pathlib import Path

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.activity.models import ActivityTask
from agentworkmemory.services.sessions.models import AgentEventKind, SessionState


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
    category: str
    tags: tuple[str, ...]
    source_session_ids: tuple[str, ...]
    backlink_count: int


class ViewerPageDetail(AgentWorkMemoryModel):
    path: Path
    title: str
    category: str
    html: str
    backlinks: tuple[ViewerPage, ...]


class ViewerProject(AgentWorkMemoryModel):
    path: Path
    title: str
    topic_count: int
    source_session_ids: tuple[str, ...]


class ViewerProjectDetail(AgentWorkMemoryModel):
    page: ViewerPageDetail
    topics: tuple[ViewerPage, ...]
    sessions: tuple[ViewerSession, ...]
