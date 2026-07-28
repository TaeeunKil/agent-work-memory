from agentworkmemory.services.curators.models import ContentAccess
from agentworkmemory.services.sessions.models import AgentEvent, AgentSession

MAX_EVIDENCE_CHARS = 120_000


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
        "- Preserve existing sources and append each supporting session once.",
        "- Use this exact source shape:",
        "  sources:",
        "    - session_id: ses_...",
        "      provider: codex",
        "- Cite only sessions that actually support the page.",
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
        remaining = per_session_budget
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
