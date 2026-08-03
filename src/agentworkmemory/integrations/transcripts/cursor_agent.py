from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from agentworkmemory.integrations.transcripts.models import TranscriptReadResult
from agentworkmemory.integrations.transcripts.normalize import MAX_EVENT_CONTENT_CHARS
from agentworkmemory.services.sessions.models import AgentEvent, AgentEventKind
from agentworkmemory.services.sessions.service import stable_event_id


class CursorAgentContentPart(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: str
    text: str = ""


class CursorAgentMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    content: tuple[CursorAgentContentPart, ...] = ()


class CursorAgentRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    role: Literal["user", "assistant"] | None = None
    message: CursorAgentMessage | None = None
    timestamp: str | None = None


class CursorAgentTranscript(BaseModel):
    model_config = ConfigDict(frozen=True)

    composer_id: str
    path: Path
    modified_at: datetime
    size_bytes: int


def discover_cursor_agent_transcripts(
    home: Path,
) -> tuple[CursorAgentTranscript, ...]:
    root = home / ".cursor" / "projects"
    if not root.is_dir():
        return ()
    transcripts: list[CursorAgentTranscript] = []
    for path in sorted(root.glob("*/agent-transcripts/*/*.jsonl")):
        if (
            not path.is_file()
            or path.parent.name != path.stem
            or not cursor_agent_transcript_has_messages(path)
        ):
            continue
        stat = path.stat()
        transcripts.append(
            CursorAgentTranscript(
                composer_id=path.stem,
                path=path.resolve(),
                modified_at=datetime.fromtimestamp(stat.st_mtime, UTC),
                size_bytes=stat.st_size,
            )
        )
    return tuple(transcripts)


def cursor_agent_transcript_has_messages(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as file:
            return any(
                cursor_agent_text(record)
                for raw in file
                if (record := parse_cursor_agent_record(raw)) is not None
            )
    except OSError:
        return False


def read_cursor_agent_transcript(
    content_path: Path,
    *,
    work_session_id: str,
    after_line: int,
) -> TranscriptReadResult:
    events: list[AgentEvent] = []
    last_line = 0
    with content_path.open("r", encoding="utf-8") as file:
        for line_number, raw in enumerate(file, start=1):
            last_line = line_number
            if line_number <= after_line:
                continue
            record = parse_cursor_agent_record(raw)
            if record is None:
                continue
            event = cursor_agent_record_event(
                record,
                work_session_id=work_session_id,
                source_line=line_number,
            )
            if event is not None:
                events.append(event)
    return TranscriptReadResult(
        events=tuple(events),
        last_line=last_line,
        size_bytes=content_path.stat().st_size,
    )


def parse_cursor_agent_record(raw: str) -> CursorAgentRecord | None:
    try:
        return CursorAgentRecord.model_validate_json(raw)
    except ValueError:
        return None


def cursor_agent_text(record: CursorAgentRecord) -> str:
    if record.role is None or record.message is None:
        return ""
    texts = tuple(
        normalize_cursor_agent_text(part.text, role=record.role)
        for part in record.message.content
        if part.type == "text"
    )
    return "\n\n".join(text for text in texts if text)


def normalize_cursor_agent_text(value: str, *, role: str) -> str:
    text = value.strip()
    if role == "assistant":
        if text == "[REDACTED]":
            return ""
        text = text.removesuffix("\n\n[REDACTED]").rstrip()
    opening = "<user_query>\n"
    closing = "\n</user_query>"
    marker = text.find(opening)
    if role == "user" and marker >= 0 and text.endswith(closing):
        prefix = text[:marker].strip()
        query = text[marker + len(opening) : -len(closing)].strip()
        return "\n".join(part for part in (prefix, query) if part)
    return text


def cursor_agent_record_event(
    record: CursorAgentRecord,
    *,
    work_session_id: str,
    source_line: int,
) -> AgentEvent | None:
    content = cursor_agent_text(record)[:MAX_EVENT_CONTENT_CHARS]
    if not content or record.role is None:
        return None
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
        role=record.role,
        label=record.role,
        occurred_at=parse_cursor_timestamp(record.timestamp),
        content=content,
        source_line=source_line,
        created_at=datetime.now(UTC),
    )


def parse_cursor_timestamp(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
