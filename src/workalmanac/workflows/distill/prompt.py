from workalmanac.services.curators.models import ContentAccess
from workalmanac.services.sessions.models import AgentEvent, AgentSession

MAX_EVIDENCE_CHARS = 120_000


def distill_prompt(
    selected: tuple[tuple[AgentSession, tuple[AgentEvent, ...]], ...],
    content_access: ContentAccess,
) -> str:
    lines = [
        "Distill the selected Work Almanac sessions into durable Wiki knowledge.",
        "",
        "The working directory is the private Wiki Vault.",
        "Read existing durable pages before editing.",
        "No-op if the evidence adds no durable knowledge.",
        "",
        "Allowed writes: README.md and Markdown under projects/, decisions/,",
        "problems/, procedures/, systems/, and unfinished/.",
        "Never edit inbox/agent-sessions/.",
        "",
        f"Content access: {content_access.value}",
        "",
        "Selected sessions:",
    ]
    remaining = MAX_EVIDENCE_CHARS
    for session, events in selected:
        lines.extend(
            (
                "",
                f"## {session.session_id}",
                f"- Provider: {session.provider}",
                f"- Provider session: {session.provider_session_id}",
                f"- Last observed: {session.modified_at.isoformat()}",
                f"- Evidence events: {len(events)}",
                f"- Citation target: work://session/{session.session_id}",
            )
        )
        if content_access is ContentAccess.METADATA_ONLY:
            lines.append("- Event bodies withheld by content-access policy.")
            continue
        lines.append(f"- Title: {session.title}")
        lines.extend(("", "### Selected evidence", ""))
        for event in events:
            header = (
                f"[{event.sequence}] {event.kind.value} "
                f"{event.role or '-'} · {event.label}"
            )
            available = max(0, remaining - len(header) - 2)
            if available == 0:
                lines.append("[Evidence truncated at curator boundary.]")
                break
            content = event.content[:available]
            lines.extend((header, content, ""))
            remaining -= len(header) + len(content) + 2
            if len(content) < len(event.content):
                lines.append("[Evidence truncated at curator boundary.]")
                break
    lines.extend(
        (
            "",
            "Finish by briefly stating which durable pages changed, or that the",
            "run was a no-op. Do not include transcript bodies in the final answer.",
        )
    )
    return "\n".join(lines).strip() + "\n"
