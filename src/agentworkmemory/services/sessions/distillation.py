from pathlib import Path

from agentworkmemory.services.sessions.models import AgentSession

INTERNAL_WORKSPACE_PARTS = frozenset(
    {
        ".acl-probe",
        ".pytest_cache",
        ".pytest-tmp",
        "acl-probe",
        "distill-workspaces",
    }
)


def is_distillation_candidate(
    session: AgentSession,
    state_root: Path,
) -> bool:
    return (
        session.content_captured
        and session.distilled_at is None
        and not is_internal_workspace(session.cwd, state_root)
    )


def is_internal_workspace(cwd: Path | None, state_root: Path) -> bool:
    if cwd is None:
        return False
    resolved = cwd.expanduser().resolve(strict=False)
    try:
        resolved.relative_to(state_root.expanduser().resolve(strict=False))
        return True
    except ValueError:
        pass
    parts = tuple(part.casefold() for part in resolved.parts)
    return any(part in INTERNAL_WORKSPACE_PARTS for part in parts)


def same_workspace(left: AgentSession, right: AgentSession) -> bool:
    if left.cwd is None or right.cwd is None:
        return left.session_id == right.session_id
    return (
        str(left.cwd.expanduser().resolve(strict=False)).casefold()
        == str(right.cwd.expanduser().resolve(strict=False)).casefold()
    )
