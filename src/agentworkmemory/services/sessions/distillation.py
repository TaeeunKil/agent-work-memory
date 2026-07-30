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
    resolved = normalized_workspace_path(cwd)
    try:
        resolved.relative_to(normalized_workspace_path(state_root))
        return True
    except ValueError:
        pass
    parts = tuple(part.casefold() for part in resolved.parts)
    return any(part in INTERNAL_WORKSPACE_PARTS for part in parts)


def normalized_workspace_path(path: Path) -> Path:
    expanded = path.expanduser()
    try:
        return expanded.resolve(strict=False)
    except OSError:
        return expanded.absolute()


def same_workspace(left: AgentSession, right: AgentSession) -> bool:
    if left.cwd is None or right.cwd is None:
        return left.session_id == right.session_id
    return (
        str(normalized_workspace_path(left.cwd)).casefold()
        == str(normalized_workspace_path(right.cwd)).casefold()
    )
