import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import yaml

from workalmanac.services.sessions.models import AgentEvent, AgentSession
from workalmanac.services.vault.snapshot import VaultSnapshot
from workalmanac.settings import WorkAlmanacConfig, save_config

VAULT_DIRECTORIES = (
    "inbox/agent-sessions",
    "projects",
    "decisions",
    "problems",
    "procedures",
    "systems",
    "unfinished",
    "imports/repository-almanacs",
)
DURABLE_DIRECTORIES = frozenset(
    {
        "projects",
        "decisions",
        "problems",
        "procedures",
        "systems",
        "unfinished",
    }
)
CATALOG_DIRECTORIES = DURABLE_DIRECTORIES | {"imports"}
CURATOR_IGNORED_ROOTS = frozenset({"inbox"})


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
            sorted(
                path
                for path in vault_path.rglob("*.md")
                if path.is_file() and not path.is_symlink()
            )
        )

    def snapshot(self) -> VaultSnapshot:
        return VaultSnapshot.capture(self.require_path())

    def validate_curator_source(self) -> None:
        VaultSnapshot.capture(
            self.require_path(),
            ignored_roots=CURATOR_IGNORED_ROOTS,
        )

    @contextmanager
    def curator_workspace(
        self,
    ) -> Iterator[tuple[Path, VaultSnapshot, VaultSnapshot]]:
        vault_path = self.require_path()
        original = VaultSnapshot.capture(
            vault_path,
            ignored_roots=CURATOR_IGNORED_ROOTS,
        )
        workspace_root = self.config.state_dir / "distill-workspaces"
        workspace_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="distill-",
            dir=workspace_root,
        ) as temporary:
            workspace = Path(temporary) / "vault"
            shutil.copytree(
                vault_path,
                workspace,
                ignore=shutil.ignore_patterns(".git", "inbox"),
            )
            yield workspace, VaultSnapshot.capture(workspace), original

    def validate_distill_changes(
        self,
        snapshot: VaultSnapshot,
    ) -> tuple[Path, ...]:
        changed = snapshot.changed_files()
        for relative in changed:
            if not allowed_distill_path(relative):
                raise ValueError(f"curator changed forbidden Vault path: {relative}")
            path = snapshot.root / relative
            if not path.is_file():
                raise ValueError(f"curator deleted durable Wiki page: {relative}")
            validate_markdown_page(path)
        return changed

    def apply_distill_changes(
        self,
        workspace: Path,
        changed: tuple[Path, ...],
    ) -> None:
        vault_path = self.require_path()
        originals: dict[Path, bytes | None] = {}
        try:
            for relative in changed:
                if not allowed_distill_path(relative):
                    raise ValueError(
                        f"refusing to apply forbidden Vault path: {relative}"
                    )
                source = (workspace / relative).resolve()
                ensure_inside(workspace, source)
                target = (vault_path / relative).resolve()
                ensure_inside(vault_path, target)
                originals[relative] = target.read_bytes() if target.is_file() else None
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        except Exception:
            restore_originals(vault_path, originals)
            raise


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
    if session.distilled_at is not None:
        lines.append(f"- Distilled: `{session.distilled_at.isoformat()}`")
    if session.distill_runtime is not None:
        lines.append(f"- Curator: `{session.distill_runtime}`")
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


def allowed_distill_path(relative: Path) -> bool:
    return (
        len(relative.parts) >= 2
        and relative.parts[0] in DURABLE_DIRECTORIES
        and relative.suffix.lower() == ".md"
        and relative.name != "_index.md"
    )


def validate_markdown_page(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    body = raw
    if raw.startswith("---\n"):
        closing = raw.find("\n---\n", 4)
        if closing < 0:
            raise ValueError(f"unterminated frontmatter: {path.name}")
        metadata = yaml.safe_load(raw[4:closing])
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError(f"frontmatter must be a mapping: {path.name}")
        body = raw[closing + 5 :]
    if not any(line.startswith("# ") for line in body.splitlines()):
        raise ValueError(f"Wiki page needs an H1 title: {path.name}")


def restore_originals(root: Path, originals: dict[Path, bytes | None]) -> None:
    for relative, content in originals.items():
        target = (root / relative).resolve()
        ensure_inside(root, target)
        if content is None:
            if target.is_file():
                target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def vault_readme() -> str:
    return """# Work Almanac

This is the private Wiki for work performed across agents, projects, and
environments.

Open [[Home]] for the generated Work Almanac navigation page.

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
