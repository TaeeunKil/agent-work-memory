from pathlib import Path

import yaml

from workalmanac.services.sessions.models import AgentEvent, AgentSession
from workalmanac.settings import WorkAlmanacConfig, save_config

VAULT_DIRECTORIES = (
    "inbox/agent-sessions",
    "projects",
    "decisions",
    "problems",
    "procedures",
    "systems",
    "unfinished",
)


class VaultService:
    def __init__(self, config: WorkAlmanacConfig):
        self.config = config

    def initialize(self, path: Path) -> Path:
        vault_path = path.expanduser().resolve()
        vault_path.mkdir(parents=True, exist_ok=True)
        for directory in VAULT_DIRECTORIES:
            (vault_path / directory).mkdir(parents=True, exist_ok=True)
        readme = vault_path / "README.md"
        if not readme.exists():
            readme.write_text(vault_readme(), encoding="utf-8")
        configured = WorkAlmanacConfig(
            state_dir=self.config.state_dir,
            vault_path=vault_path,
        )
        save_config(configured)
        self.config = configured
        return vault_path

    def require_path(self) -> Path:
        if self.config.vault_path is None:
            raise RuntimeError("Work Almanac is not initialized; run `wa init <path>`")
        return self.config.vault_path

    def refresh_session(
        self,
        session: AgentSession,
        events: tuple[AgentEvent, ...],
    ) -> Path:
        vault_path = self.require_path()
        target = (
            vault_path
            / "inbox"
            / "agent-sessions"
            / f"{session.provider}-{session.session_id}.md"
        ).resolve()
        ensure_inside(vault_path, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_session_page(session, events), encoding="utf-8")
        return target

    def markdown_files(self) -> tuple[Path, ...]:
        vault_path = self.require_path()
        return tuple(
            sorted(path for path in vault_path.rglob("*.md") if path.is_file())
        )


def render_session_page(
    session: AgentSession,
    events: tuple[AgentEvent, ...],
) -> str:
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
        yaml.safe_dump(
            frontmatter,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip(),
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
    lines.extend(("", "## Record", ""))
    if not events:
        lines.extend(
            (
                "Transcript content has not been imported.",
                "",
                "Run `wa collect --include-content` to retain local content.",
            )
        )
    else:
        for event in events:
            lines.extend(render_event(event))
    return "\n".join(lines).rstrip() + "\n"


def render_event(event: AgentEvent) -> tuple[str, ...]:
    timestamp = (
        f" · {event.occurred_at.isoformat()}" if event.occurred_at is not None else ""
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


def ensure_inside(root: Path, target: Path) -> None:
    try:
        target.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError(f"Wiki path escapes configured Vault: {target}") from error


def vault_readme() -> str:
    return """# Work Almanac

This is the private Wiki for work performed across agents, projects, and
environments.

## Areas

- [Agent session inbox](inbox/agent-sessions/)
- [Projects](projects/)
- [Decisions](decisions/)
- [Problems](problems/)
- [Procedures](procedures/)
- [Systems](systems/)
- [Unfinished work](unfinished/)

Agent session pages are retained records. Promote conclusions worth remembering
into the durable Wiki areas above.
"""
