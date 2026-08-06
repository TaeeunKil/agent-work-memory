import yaml

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.sessions.models import AgentEvent, AgentSession

SESSION_RECORD_PART_BYTES = 16 * 1024 * 1024
PART_HEADER_RESERVE_BYTES = 4 * 1024


class SessionRecordPart(AgentWorkMemoryModel):
    number: int
    first_sequence: int
    last_sequence: int
    content: str

    @property
    def filename(self) -> str:
        return f"part-{self.number:03d}.md"


class SessionRecordBundle(AgentWorkMemoryModel):
    index_content: str
    parts: tuple[SessionRecordPart, ...] = ()


def render_session_record(
    session: AgentSession,
    events: tuple[AgentEvent, ...],
    *,
    target_bytes: int | None = None,
) -> SessionRecordBundle:
    byte_budget = (
        SESSION_RECORD_PART_BYTES if target_bytes is None else target_bytes
    )
    if byte_budget <= PART_HEADER_RESERVE_BYTES * 2:
        raise ValueError("session record part budget is too small")
    complete = render_session_page(session, events)
    if len(complete.encode("utf-8")) <= byte_budget:
        return SessionRecordBundle(index_content=complete)

    blocks = tuple(
        block
        for event in events
        for block in render_event_fragments(
            event,
            max_content_bytes=byte_budget - PART_HEADER_RESERVE_BYTES * 2,
        )
    )
    grouped = group_event_blocks(
        blocks,
        max_body_bytes=byte_budget - PART_HEADER_RESERVE_BYTES,
    )
    stem = f"{session.provider}-{session.session_id}"
    parts = tuple(
        render_part(session, stem, number, group)
        for number, group in enumerate(grouped, start=1)
    )
    if any(len(part.content.encode("utf-8")) > byte_budget for part in parts):
        raise ValueError("session record metadata exceeds the part byte budget")
    return SessionRecordBundle(
        index_content=render_session_index(session, stem, parts),
        parts=parts,
    )


def render_session_page(
    session: AgentSession,
    events: tuple[AgentEvent, ...],
) -> str:
    lines = session_header(session)
    lines.extend(("", "## Record", ""))
    if not events:
        lines.extend(
            (
                "Transcript content has not been imported.",
                "",
                "Run `awm collect --include-content` to retain local content.",
            )
        )
    else:
        for event in events:
            lines.extend(render_event(event))
    return "\n".join(lines).rstrip() + "\n"


def render_session_index(
    session: AgentSession,
    stem: str,
    parts: tuple[SessionRecordPart, ...],
) -> str:
    lines = session_header(session)
    lines.extend(
        (
            "",
            "## Record parts",
            "",
            f"This retained session is stored in {len(parts)} bounded parts.",
            "",
        )
    )
    for part in parts:
        label = f"Part {part.number}: events {part.first_sequence}–{part.last_sequence}"
        lines.append(f"- [[inbox/agent-sessions/{stem}/{part.filename}|{label}]]")
    return "\n".join(lines).rstrip() + "\n"


def render_part(
    session: AgentSession,
    stem: str,
    number: int,
    blocks: tuple[tuple[int, str], ...],
) -> SessionRecordPart:
    first_sequence = blocks[0][0]
    last_sequence = blocks[-1][0]
    metadata = {
        "id": f"{session.session_id}-part-{number:03d}",
        "title": f"{session.title} — Part {number}",
        "tags": ["agent-session-part", session.provider],
        "session_id": session.session_id,
        "part": number,
        "sources": [
            {
                "id": f"{session.provider}-session",
                "type": "conversation",
                "session_id": session.provider_session_id,
            }
        ],
    }
    lines = [
        "---",
        yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).rstrip(),
        "---",
        f"# {session.title} — Part {number}",
        "",
        f"- Session: [[inbox/agent-sessions/{stem}|{session.title}]]",
        f"- Events: `{first_sequence}`–`{last_sequence}`",
        "",
        "## Record",
        "",
    ]
    lines.extend(block for _, block in blocks)
    return SessionRecordPart(
        number=number,
        first_sequence=first_sequence,
        last_sequence=last_sequence,
        content="\n".join(lines).rstrip() + "\n",
    )


def session_header(session: AgentSession) -> list[str]:
    frontmatter = {
        "id": session.session_id,
        "title": session.title,
        "tags": ["agent-session", session.provider],
        "sources": [
            {
                "id": f"{session.provider}-session",
                "type": "conversation",
                "session_id": session.provider_session_id,
            }
        ],
    }
    lines = [
        "---",
        yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).rstrip(),
        "---",
        f"# {session.title}",
        "",
        f"- Agent: `{session.provider}`",
        f"- Session: `{session.provider_session_id}`",
        f"- State: `{session.state.value}`",
        f"- Last observed: `{session.modified_at.isoformat()}`",
    ]
    if session.cwd is not None:
        lines.append(f"- Workspace: `{session.cwd}`")
    if session.distilled_at is not None:
        lines.append(f"- Distilled: `{session.distilled_at.isoformat()}`")
    if session.distill_runtime is not None:
        lines.append(f"- Curator: `{session.distill_runtime}`")
    return lines


def render_event_fragments(
    event: AgentEvent,
    *,
    max_content_bytes: int,
) -> tuple[tuple[int, str], ...]:
    chunks = split_utf8(event.content, max_content_bytes)
    total = len(chunks)
    return tuple(
        (
            event.sequence,
            "\n".join(
                render_event(
                    event.model_copy(
                        update={
                            "label": (
                                event.label
                                if total == 1
                                else f"{event.label} (continuation {number}/{total})"
                            ),
                            "content": chunk,
                        }
                    )
                )
            ).rstrip(),
        )
        for number, chunk in enumerate(chunks, start=1)
    )


def group_event_blocks(
    blocks: tuple[tuple[int, str], ...],
    *,
    max_body_bytes: int,
) -> tuple[tuple[tuple[int, str], ...], ...]:
    groups: list[tuple[tuple[int, str], ...]] = []
    current: list[tuple[int, str]] = []
    current_bytes = 0
    for block in blocks:
        block_bytes = len(block[1].encode("utf-8")) + 2
        if current and current_bytes + block_bytes > max_body_bytes:
            groups.append(tuple(current))
            current = []
            current_bytes = 0
        current.append(block)
        current_bytes += block_bytes
    if current:
        groups.append(tuple(current))
    return tuple(groups)


def split_utf8(content: str, max_bytes: int) -> tuple[str, ...]:
    if max_bytes <= 0:
        raise ValueError("event content byte budget must be positive")
    if len(content.encode("utf-8")) <= max_bytes:
        return (content,)
    chunks: list[str] = []
    start = 0
    while start < len(content):
        low = start + 1
        high = len(content)
        best = start
        while low <= high:
            middle = (low + high) // 2
            if len(content[start:middle].encode("utf-8")) <= max_bytes:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        if best == start:
            raise ValueError("event content byte budget cannot fit one character")
        chunks.append(content[start:best])
        start = best
    return tuple(chunks)


def render_event(event: AgentEvent) -> tuple[str, ...]:
    timestamp = (
        f" • {event.occurred_at.isoformat()}" if event.occurred_at is not None else ""
    )
    fence = safe_fence(event.content)
    return (
        f"### {event.sequence}. {event.label}{timestamp}",
        "",
        f"{fence}text",
        event.content,
        fence,
        "",
    )


def safe_fence(content: str) -> str:
    longest = 0
    current = 0
    for character in content:
        if character == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return "`" * max(3, longest + 1)
