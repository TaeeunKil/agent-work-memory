import json
from datetime import UTC, datetime
from pathlib import Path

from agentworkmemory.integrations.transcripts.models import (
    DiscoveredAgentSession,
    TranscriptReadResult,
)
from agentworkmemory.integrations.transcripts.normalize import (
    CODEX_NORMALIZER_VERSION,
    normalize_transcript_line,
)
from agentworkmemory.services.sessions.models import (
    AgentEvent,
    AgentEventKind,
    AgentProvider,
    AgentProviderId,
    SessionState,
)

CLAUDE_NORMALIZER_VERSION = "claude-v1"


class CodexTranscriptCollector:
    provider = AgentProvider.CODEX

    def __init__(self, sessions_dir: Path | None = None):
        self.sessions_dir = sessions_dir

    def discover(self, home: Path) -> tuple[DiscoveredAgentSession, ...]:
        roots = (
            ((self.sessions_dir, SessionState.OPEN),)
            if self.sessions_dir is not None
            else (
                (home / ".codex" / "sessions", SessionState.OPEN),
                (home / ".codex" / "archived_sessions", SessionState.COMPLETE),
            )
        )
        discovered: dict[str, DiscoveredAgentSession] = {}
        for root, state in roots:
            for path in jsonl_files(root):
                meta = codex_metadata(path)
                if meta is None or meta[2] == "subagent":
                    continue
                session_id, cwd, _ = meta
                candidate = discovered_session(
                    provider=self.provider,
                    provider_session_id=session_id,
                    cwd=cwd,
                    path=path,
                    state=state,
                    normalizer_version=CODEX_NORMALIZER_VERSION,
                    source_identity=f"codex:{session_id}",
                )
                existing = discovered.get(session_id)
                if existing is None or candidate.state is SessionState.OPEN:
                    discovered[session_id] = candidate
        return tuple(discovered.values())

    def read(
        self,
        session: DiscoveredAgentSession,
        *,
        work_session_id: str,
        after_line: int,
    ) -> TranscriptReadResult:
        return read_transcript(
            session,
            work_session_id=work_session_id,
            after_line=after_line,
        )


class ClaudeTranscriptCollector:
    provider = AgentProvider.CLAUDE

    def __init__(self, projects_dir: Path | None = None):
        self.projects_dir = projects_dir

    def discover(self, home: Path) -> tuple[DiscoveredAgentSession, ...]:
        root = self.projects_dir or home / ".claude" / "projects"
        discovered: list[DiscoveredAgentSession] = []
        for path in jsonl_files(root):
            if "subagents" in path.parts:
                continue
            meta = claude_metadata(path)
            if meta is None:
                continue
            session_id, cwd = meta
            discovered.append(
                discovered_session(
                    provider=self.provider,
                    provider_session_id=session_id,
                    cwd=cwd,
                    path=path,
                    normalizer_version=CLAUDE_NORMALIZER_VERSION,
                )
            )
        return tuple(discovered)

    def read(
        self,
        session: DiscoveredAgentSession,
        *,
        work_session_id: str,
        after_line: int,
    ) -> TranscriptReadResult:
        return read_transcript(
            session,
            work_session_id=work_session_id,
            after_line=after_line,
        )


def read_transcript(
    session: DiscoveredAgentSession,
    *,
    work_session_id: str,
    after_line: int,
) -> TranscriptReadResult:
    candidates: list[tuple[str, AgentEvent]] = []
    last_line = 0
    context_after_line = (
        max(0, after_line - 8)
        if session.provider == AgentProvider.CODEX
        else after_line
    )
    with session.source_path.open("r", encoding="utf-8") as file:
        for line_number, raw in enumerate(file, start=1):
            last_line = line_number
            if line_number <= context_after_line:
                continue
            parsed = parse_object(raw)
            if parsed is None:
                continue
            event = normalize_transcript_line(
                session.provider,
                work_session_id,
                line_number,
                parsed,
            )
            if event is not None:
                candidates.append((str(parsed.get("type") or ""), event))
    normalized = (
        deduplicate_codex_messages(candidates)
        if session.provider == AgentProvider.CODEX
        else tuple(event for _, event in candidates)
    )
    events = tuple(event for event in normalized if event.source_line > after_line)
    return TranscriptReadResult(
        events=events,
        last_line=last_line,
        size_bytes=session.source_path.stat().st_size,
    )


def discovered_session(
    *,
    provider: AgentProviderId,
    provider_session_id: str,
    cwd: str,
    path: Path,
    state: SessionState = SessionState.OPEN,
    normalizer_version: str = "legacy",
    source_identity: str | None = None,
) -> DiscoveredAgentSession:
    stat = path.stat()
    return DiscoveredAgentSession(
        provider=provider,
        provider_session_id=provider_session_id,
        cwd=Path(cwd).expanduser(),
        source_path=path.resolve(),
        modified_at=datetime.fromtimestamp(stat.st_mtime, UTC),
        size_bytes=stat.st_size,
        ended_at=(
            datetime.fromtimestamp(stat.st_mtime, UTC)
            if state is SessionState.COMPLETE
            else None
        ),
        state=state,
        source_identity=source_identity,
        normalizer_version=normalizer_version,
    )


def deduplicate_codex_messages(
    candidates: list[tuple[str, AgentEvent]],
) -> tuple[AgentEvent, ...]:
    response_lines: dict[tuple[str | None, str], list[int]] = {}
    for record_type, event in candidates:
        if (
            record_type != "response_item"
            or event.kind is not AgentEventKind.MESSAGE
        ):
            continue
        key = (event.role, event.content)
        response_lines.setdefault(key, []).append(event.source_line)
    retained: list[AgentEvent] = []
    for record_type, event in candidates:
        key = (event.role, event.content)
        nearby_response = any(
            abs(event.source_line - line) <= 8
            for line in response_lines.get(key, ())
        )
        if (
            record_type == "event_msg"
            and event.kind is AgentEventKind.MESSAGE
            and nearby_response
        ):
            continue
        retained.append(event)
    return tuple(retained)


def jsonl_files(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    return tuple(sorted(path for path in root.rglob("*.jsonl") if path.is_file()))


def codex_metadata(path: Path) -> tuple[str, str, str | None] | None:
    for parsed in first_objects(path):
        payload = parsed.get("payload")
        if not isinstance(payload, dict):
            continue
        session_id = payload.get("id")
        cwd = payload.get("cwd")
        thread_source = payload.get("thread_source")
        if isinstance(session_id, str) and isinstance(cwd, str):
            return (
                session_id,
                cwd,
                thread_source if isinstance(thread_source, str) else None,
            )
    return None


def claude_metadata(path: Path) -> tuple[str, str] | None:
    for parsed in first_objects(path):
        session_id = parsed.get("sessionId")
        cwd = parsed.get("cwd")
        if isinstance(session_id, str) and isinstance(cwd, str):
            return session_id, cwd
    return None


def first_objects(path: Path, limit: int = 20) -> tuple[dict[str, object], ...]:
    objects: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8") as file:
            for _ in range(limit):
                line = file.readline()
                if line == "":
                    break
                parsed = parse_object(line)
                if parsed is not None:
                    objects.append(parsed)
    except OSError:
        return ()
    return tuple(objects)


def parse_object(raw: str) -> dict[str, object] | None:
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    return {str(key): value for key, value in parsed.items()}
