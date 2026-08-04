from dataclasses import dataclass

from agentworkmemory.services.curators.models import ContentAccess
from agentworkmemory.services.sessions.models import AgentEvent, AgentSession

MAX_EVIDENCE_CHARS = 120_000
FIRST_INTENT_CHARS = 2_000
RECENT_EVENT_CHARS = 8_000


@dataclass(frozen=True)
class EvidenceExcerpt:
    event: AgentEvent
    content: str
    truncated: bool


def distill_prompt(
    selected: tuple[tuple[AgentSession, tuple[AgentEvent, ...]], ...],
    content_access: ContentAccess,
) -> str:
    lines = [
        "Distill the selected Agent Work Memory sessions into durable Wiki knowledge.",
        "",
        "The working directory is the private Wiki Vault.",
        "Read existing durable pages before editing.",
        "No-op if the evidence adds no durable knowledge.",
        "",
        "Knowledge model:",
        "- A durable page is one canonical topic, never a session summary.",
        "- Merge new evidence into an existing page when its topic matches.",
        "- Do not create duplicate pages for different agents, sessions, or dates.",
        "- Never use a session id, provider name, or date as a topic filename.",
        "- Preserve useful existing knowledge and reconcile newer evidence.",
        "",
        "Project model:",
        "- Infer the project primarily from the session workspace or repository.",
        "- Maintain one projects/<project-slug>.md hub for each project.",
        "- Link every project-specific topic page to its project hub.",
        "- Link the project hub back to its durable topic pages.",
        "- Put genuinely shared knowledge in systems/ and link all relevant projects.",
        "",
        "Source contract:",
        "- Every changed durable page must have YAML frontmatter.",
        "- When updating a page, preserve every existing frontmatter field;",
        "  never rebuild frontmatter from memory.",
        "- Preserve existing sources and append each supporting session once.",
        "- Use this exact source shape:",
        "  sources:",
        "    - session_id: ses_...",
        "      provider: codex",
        "- Cite only sessions that actually support the page.",
        "",
        "Graph title contract:",
        "- Every changed durable page must define both short_title_ko and",
        "  short_title_en in YAML frontmatter.",
        "- Every changed durable page must define language as ko or en for",
        "  the canonical body.",
        "- Write semantic labels, not mechanically truncated H1 text.",
        "- Keep Korean labels concise (about 24 characters) and English labels",
        "  concise (about 6 words), preserving product names and acronyms.",
        "- Use one line without a trailing period, and update both labels when",
        "  the page topic or H1 materially changes.",
        "",
        "Allowed writes: non-index Markdown under projects/, decisions/,",
        "problems/, procedures/, systems/, and unfinished/.",
        "Never edit README.md, Home.md, _index.md, or inbox/agent-sessions/.",
        "Use Vault-relative [[Wiki links]] between related durable pages.",
        "",
        f"Content access: {content_access.value}",
        "",
        "Selected sessions:",
    ]
    per_session_budget = MAX_EVIDENCE_CHARS // max(1, len(selected))
    for session, events in selected:
        session_alias = (
            session.title
            if content_access is not ContentAccess.METADATA_ONLY
            else f"{session.provider} session {session.session_id}"
        )
        lines.extend(
            (
                "",
                f"## {session.session_id}",
                f"- Provider: {session.provider}",
                f"- Provider session: {session.provider_session_id}",
                f"- Workspace: {session.cwd or 'unknown'}",
                f"- Last observed: {session.modified_at.isoformat()}",
                f"- Evidence events: {len(events)}",
                f"- Citation target: work://session/{session.session_id}",
                "- Session Wiki link: "
                f"[[inbox/agent-sessions/{session.provider}-{session.session_id}"
                f"|{session_alias}]]",
            )
        )
        if content_access is ContentAccess.METADATA_ONLY:
            lines.append("- Event bodies withheld by content-access policy.")
            continue
        lines.append(f"- Title: {session.title}")
        lines.extend(("", "### Selected evidence", ""))
        excerpts = select_evidence(events, per_session_budget)
        if len(excerpts) < len(events):
            lines.append(
                f"[Selected {len(excerpts)} of {len(events)} events: "
                "opening intent and recent conversational outcomes.]"
            )
        for item in excerpts:
            lines.extend((event_header(item.event), item.content, ""))
            if item.truncated:
                lines.append("[Event excerpt truncated at curator boundary.]")
    lines.extend(
        (
            "",
            "Finish by briefly stating which durable pages changed, or that the",
            "run was a no-op. Do not include transcript bodies in the final answer.",
        )
    )
    return "\n".join(lines).strip() + "\n"


def select_evidence(
    events: tuple[AgentEvent, ...],
    budget: int,
) -> tuple[EvidenceExcerpt, ...]:
    if budget <= 0 or not events:
        return ()
    conversational = tuple(
        event
        for event in events
        if event.role in {"user", "assistant"}
        or event.kind.value in {"message", "note"}
    )
    candidates = conversational or events
    first = candidates[0]
    if len(candidates) == 1:
        available = max(0, budget - len(event_header(first)) - 2)
        return (excerpt(first, available),)

    first_budget = min(
        FIRST_INTENT_CHARS,
        max(1, budget // 3),
        max(0, budget - len(event_header(first)) - 2),
    )
    selected = [excerpt(first, first_budget)]
    remaining = budget - len(event_header(first)) - len(selected[0].content) - 2
    recent: list[EvidenceExcerpt] = []
    for event in reversed(candidates[1:]):
        available = remaining - len(event_header(event)) - 2
        if available <= 0:
            break
        item = excerpt(event, min(RECENT_EVENT_CHARS, available))
        recent.append(item)
        remaining -= len(event_header(event)) + len(item.content) + 2
    selected.extend(reversed(recent))
    return tuple(selected)


def excerpt(event: AgentEvent, limit: int) -> EvidenceExcerpt:
    content = event.content[: max(0, limit)]
    return EvidenceExcerpt(
        event=event,
        content=content,
        truncated=len(content) < len(event.content),
    )


def event_header(event: AgentEvent) -> str:
    return (
        f"[{event.sequence}] {event.kind.value} "
        f"{event.role or '-'} · {event.label}"
    )
