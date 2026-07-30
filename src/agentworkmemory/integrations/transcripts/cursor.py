import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname

from pydantic import BaseModel, ConfigDict, Field

from agentworkmemory.integrations.transcripts.models import (
    DiscoveredAgentSession,
    TranscriptReadResult,
)
from agentworkmemory.integrations.transcripts.normalize import MAX_EVENT_CONTENT_CHARS
from agentworkmemory.services.sessions.models import (
    AgentEvent,
    AgentEventKind,
    AgentProvider,
)
from agentworkmemory.services.sessions.service import stable_event_id


class CursorUri(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    external: str


class CursorWorkspaceIdentifier(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    uri: str | CursorUri | None = None


class CursorComposerHeader(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    composer_id: str = Field(alias="composerId")
    name: str = ""
    created_at: int | None = Field(default=None, alias="createdAt")
    last_updated_at: int | None = Field(default=None, alias="lastUpdatedAt")
    workspace_identifier: CursorWorkspaceIdentifier | None = Field(
        default=None,
        alias="workspaceIdentifier",
    )


class CursorBubble(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    bubble_id: str = Field(alias="bubbleId")
    type: Literal[1, 2]
    text: str = ""
    created_at: str | None = Field(default=None, alias="createdAt")


class CursorTranscriptCollector:
    provider = AgentProvider.CURSOR

    def __init__(self, user_storage_dir: Path | None = None):
        self.user_storage_dir = user_storage_dir
        self.bubbles_by_composer: dict[str, tuple[CursorBubble, ...]] | None = None

    def discover(self, home: Path) -> tuple[DiscoveredAgentSession, ...]:
        database_path = self.database_path(home)
        if database_path is None:
            return ()
        stat = database_path.stat()
        self.bubbles_by_composer = None
        with cursor_snapshot(database_path) as connection:
            headers = read_headers(connection)
        return tuple(
            DiscoveredAgentSession(
                provider=self.provider,
                provider_session_id=header.composer_id,
                title=header.name.strip() or None,
                cwd=cursor_workspace_path(header),
                source_path=database_path.resolve(),
                started_at=milliseconds_datetime(header.created_at),
                modified_at=(
                    milliseconds_datetime(header.last_updated_at)
                    or datetime.fromtimestamp(stat.st_mtime, UTC)
                ),
                size_bytes=stat.st_size,
            )
            for header in headers
        )

    def read(
        self,
        session: DiscoveredAgentSession,
        *,
        work_session_id: str,
        after_line: int,
    ) -> TranscriptReadResult:
        del after_line
        bubbles = self.bubbles(session)
        events = tuple(
            cursor_event(
                bubble,
                work_session_id=work_session_id,
                source_line=source_line,
            )
            for source_line, bubble in enumerate(bubbles, start=1)
            if bubble.text.strip()
        )
        return TranscriptReadResult(
            events=events,
            last_line=len(bubbles),
            size_bytes=session.source_path.stat().st_size,
        )

    def bubbles(
        self,
        session: DiscoveredAgentSession,
    ) -> tuple[CursorBubble, ...]:
        if self.bubbles_by_composer is None:
            with cursor_snapshot(session.source_path) as connection:
                self.bubbles_by_composer = read_all_bubbles(connection)
        return self.bubbles_by_composer.get(session.provider_session_id, ())

    def database_path(self, home: Path) -> Path | None:
        roots = (
            (self.user_storage_dir,)
            if self.user_storage_dir is not None
            else cursor_user_storage_candidates(home)
        )
        for root in roots:
            path = root / "globalStorage" / "state.vscdb"
            if path.is_file():
                return path
        return None


def cursor_user_storage_candidates(home: Path) -> tuple[Path, ...]:
    return (
        home / "AppData" / "Roaming" / "Cursor" / "User",
        home / "Library" / "Application Support" / "Cursor" / "User",
        home / ".config" / "Cursor" / "User",
    )


@contextmanager
def cursor_snapshot(database_path: Path) -> Iterator[sqlite3.Connection]:
    source = sqlite3.connect(
        f"{database_path.resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=5,
    )
    snapshot = sqlite3.connect(":memory:")
    try:
        source.backup(snapshot)
        snapshot.row_factory = sqlite3.Row
        yield snapshot
    finally:
        snapshot.close()
        source.close()


def read_headers(connection: sqlite3.Connection) -> tuple[CursorComposerHeader, ...]:
    if not table_exists(connection, "composerHeaders"):
        return ()
    rows = connection.execute(
        "SELECT value FROM composerHeaders ORDER BY lastUpdatedAt, composerId"
    ).fetchall()
    headers: list[CursorComposerHeader] = []
    for row in rows:
        try:
            headers.append(CursorComposerHeader.model_validate_json(row["value"]))
        except ValueError:
            continue
    return tuple(headers)


def read_all_bubbles(
    connection: sqlite3.Connection,
) -> dict[str, tuple[CursorBubble, ...]]:
    if not table_exists(connection, "cursorDiskKV"):
        return {}
    rows = connection.execute(
        "SELECT key, value FROM cursorDiskKV WHERE key LIKE 'bubbleId:%'",
    ).fetchall()
    grouped: dict[str, list[CursorBubble]] = {}
    for row in rows:
        try:
            bubble = CursorBubble.model_validate_json(row["value"])
        except ValueError:
            continue
        key_parts = row["key"].split(":", 2)
        if len(key_parts) != 3:
            continue
        grouped.setdefault(key_parts[1], []).append(bubble)
    return {
        composer_id: tuple(
            sorted(
                bubbles,
                key=lambda item: (item.created_at or "", item.bubble_id),
            )
        )
        for composer_id, bubbles in grouped.items()
    }


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def cursor_event(
    bubble: CursorBubble,
    *,
    work_session_id: str,
    source_line: int,
) -> AgentEvent:
    role = "user" if bubble.type == 1 else "assistant"
    content = bubble.text.strip()[:MAX_EVENT_CONTENT_CHARS]
    return AgentEvent(
        event_id=stable_event_id(
            session_id=work_session_id,
            source_line=source_line,
            kind=AgentEventKind.MESSAGE,
            content=content,
        ),
        session_id=work_session_id,
        sequence=source_line,
        kind=AgentEventKind.MESSAGE,
        role=role,
        label=role,
        occurred_at=parse_cursor_timestamp(bubble.created_at),
        content=content,
        source_line=source_line,
        created_at=datetime.now(UTC),
    )


def cursor_workspace_path(header: CursorComposerHeader) -> Path | None:
    identifier = header.workspace_identifier
    if identifier is None or identifier.uri is None:
        return None
    uri = (
        identifier.uri
        if isinstance(identifier.uri, str)
        else identifier.uri.external
    )
    parsed = urlsplit(uri)
    path = unquote(parsed.path)
    if parsed.scheme == "file":
        return Path(url2pathname(path))
    if parsed.scheme != "vscode-remote" or not parsed.netloc:
        return None
    authority = unquote(parsed.netloc)
    if authority.startswith("wsl+"):
        distro = authority.removeprefix("wsl+")
        return Path(f"//wsl.localhost/{distro}{path}")
    for prefix in ("ssh-remote+", "ssh+"):
        if authority.startswith(prefix):
            host = authority.removeprefix(prefix)
            return Path(f"//cursor-ssh/{host}{path}")
    return Path(f"//cursor-remote/{authority}{path}")


def milliseconds_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, UTC)


def parse_cursor_timestamp(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
