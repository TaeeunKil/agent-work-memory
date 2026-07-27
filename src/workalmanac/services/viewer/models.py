from datetime import datetime
from pathlib import Path

from workalmanac.core import WorkAlmanacModel
from workalmanac.services.sessions.models import AgentEventKind, SessionState


class ViewerOverview(WorkAlmanacModel):
    session_count: int
    knowledge_count: int
    pending_distill_count: int
    last_sync_status: str | None
    last_sync_at: datetime | None


class ViewerSession(WorkAlmanacModel):
    session_id: str
    provider: str
    title: str
    state: SessionState
    modified_at: datetime
    content_captured: bool
    distilled_at: datetime | None
    event_count: int


class ViewerEvent(WorkAlmanacModel):
    sequence: int
    kind: AgentEventKind
    role: str | None
    label: str
    occurred_at: datetime | None
    content: str


class ViewerSessionDetail(WorkAlmanacModel):
    session: ViewerSession
    workspace: str | None
    events: tuple[ViewerEvent, ...]


class ViewerPage(WorkAlmanacModel):
    path: Path
    title: str
    category: str
    tags: tuple[str, ...]
    source_session_ids: tuple[str, ...]
    backlink_count: int


class ViewerPageDetail(WorkAlmanacModel):
    path: Path
    title: str
    category: str
    html: str
    backlinks: tuple[ViewerPage, ...]
