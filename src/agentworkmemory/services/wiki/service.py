import re
from collections import defaultdict
from pathlib import Path

import yaml

from agentworkmemory.services.sessions.models import AgentSession
from agentworkmemory.services.sessions.service import SessionsService
from agentworkmemory.services.vault.service import CATALOG_DIRECTORIES, VaultService
from agentworkmemory.services.wiki.models import WikiPage, WikiPageLink

HOME_PATH = Path("Home.md")
INDEX_NAME = "_index.md"
WIKILINK = re.compile(r"\[\[([^\]#|]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
CATEGORY_TITLES = {
    "projects": "Projects",
    "decisions": "Decisions",
    "problems": "Problems",
    "procedures": "Procedures",
    "systems": "Systems",
    "unfinished": "Unfinished work",
    "imports": "Imported Almanacs",
}


class WikiCatalogService:
    def __init__(self, vault: VaultService, sessions: SessionsService):
        self.vault = vault
        self.sessions = sessions

    def pages(self) -> tuple[WikiPage, ...]:
        root = self.vault.require_path()
        pages: list[WikiPage] = []
        for category in sorted(CATALOG_DIRECTORIES):
            category_root = root / category
            for path in sorted(category_root.rglob("*.md")):
                if path.name == INDEX_NAME or not path.is_file() or path.is_symlink():
                    continue
                try:
                    pages.append(read_wiki_page(root, path, category))
                except (OSError, UnicodeError, yaml.YAMLError):
                    continue
        return tuple(pages)

    def refresh(self) -> tuple[Path, ...]:
        root = self.vault.require_path()
        pages = self.pages()
        sessions = self.sessions.list()
        backlinks = wiki_backlinks(pages)
        rendered: dict[Path, str] = {
            HOME_PATH: render_home(pages, sessions),
        }
        for category in sorted(CATALOG_DIRECTORIES):
            category_pages = tuple(page for page in pages if page.category == category)
            rendered[Path(category) / INDEX_NAME] = render_category_index(
                category,
                category_pages,
                backlinks,
                sessions,
            )
        changed: list[Path] = []
        for relative, content in rendered.items():
            target = (root / relative).resolve()
            target.relative_to(root.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_file() and target.read_text(encoding="utf-8") == content:
                continue
            target.write_text(content, encoding="utf-8")
            changed.append(relative)
        return tuple(changed)


def read_wiki_page(root: Path, path: Path, category: str) -> WikiPage:
    raw = path.read_text(encoding="utf-8")
    metadata, body = split_frontmatter(raw)
    title = markdown_title(path, body)
    tags = string_tuple(metadata.get("tags"))
    source_session_ids: list[str] = []
    sources = metadata.get("sources")
    if isinstance(sources, list):
        for source in sources:
            if not isinstance(source, dict):
                continue
            session_id = source.get("session_id")
            if isinstance(session_id, str) and session_id.startswith("ses_"):
                source_session_ids.append(session_id)
    outgoing = tuple(
        dict.fromkeys(normalize_wikilink(match) for match in WIKILINK.findall(body))
    )
    return WikiPage(
        path=path.relative_to(root),
        title=title,
        category=category,
        tags=tags,
        source_session_ids=tuple(dict.fromkeys(source_session_ids)),
        outgoing_links=outgoing,
    )


def split_frontmatter(raw: str) -> tuple[dict[str, object], str]:
    if not raw.startswith("---\n"):
        return {}, raw
    closing = raw.find("\n---\n", 4)
    if closing < 0:
        return {}, raw
    loaded = yaml.safe_load(raw[4:closing])
    metadata = (
        {str(key): value for key, value in loaded.items()}
        if isinstance(loaded, dict)
        else {}
    )
    return metadata, raw[closing + 5 :]


def markdown_title(path: Path, body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            if title:
                return title
    return path.stem.replace("-", " ").replace("_", " ").title()


def string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def normalize_wikilink(value: str) -> Path:
    normalized = value.strip().replace("\\", "/").lstrip("/")
    if normalized.lower().endswith(".md"):
        normalized = normalized[:-3]
    return Path(f"{normalized}.md")


def wiki_backlinks(pages: tuple[WikiPage, ...]) -> dict[Path, tuple[WikiPage, ...]]:
    by_path = {page.path: page for page in pages}
    incoming: dict[Path, list[WikiPage]] = defaultdict(list)
    for link in resolved_wiki_links(pages):
        incoming[link.target_path].append(by_path[link.source_path])
    return {
        path: tuple(sorted(sources, key=lambda page: page.title.casefold()))
        for path, sources in incoming.items()
    }


def resolved_wiki_links(pages: tuple[WikiPage, ...]) -> tuple[WikiPageLink, ...]:
    exact = {page.path: page.path for page in pages}
    by_stem: dict[str, list[Path]] = defaultdict(list)
    for page in pages:
        by_stem[page.path.stem.casefold()].append(page.path)
    links: list[WikiPageLink] = []
    seen: set[tuple[Path, Path]] = set()
    for page in pages:
        for link in page.outgoing_links:
            target = exact.get(link)
            if target is None and len(link.parts) == 1:
                candidates = by_stem[link.stem.casefold()]
                target = candidates[0] if len(candidates) == 1 else None
            identity = (page.path, target) if target is not None else None
            if target is not None and target != page.path and identity not in seen:
                seen.add(identity)
                links.append(
                    WikiPageLink(
                        source_path=page.path,
                        target_path=target,
                    )
                )
    return tuple(links)


def render_home(
    pages: tuple[WikiPage, ...],
    sessions: tuple[AgentSession, ...],
) -> str:
    lines = [
        "---",
        "agentworkmemory_managed: true",
        "type: home",
        "---",
        "# Agent Work Memory",
        "",
        "Your private memory of work performed with coding agents.",
        "",
        "## Knowledge",
        "",
    ]
    for category, title in CATEGORY_TITLES.items():
        count = sum(page.category == category for page in pages)
        lines.append(f"- [[{category}/{INDEX_NAME[:-3]}|{title}]] · {count}")
    lines.extend(("", "## Recent agent sessions", ""))
    for session in sessions[:12]:
        lines.append(f"- {session_link(session)}")
    if not sessions:
        lines.append("- No agent sessions retained yet.")
    pending = tuple(
        session
        for session in sessions
        if session.content_captured and session.distilled_at is None
    )
    lines.extend(("", "## Waiting to be distilled", ""))
    for session in pending[:12]:
        lines.append(f"- {session_link(session)}")
    if not pending:
        lines.append("- Nothing waiting.")
    lines.extend(
        (
            "",
            "## Record layer",
            "",
            "- [[inbox/agent-sessions|All retained agent sessions]]",
        )
    )
    return "\n".join(lines).rstrip() + "\n"


def render_category_index(
    category: str,
    pages: tuple[WikiPage, ...],
    backlinks: dict[Path, tuple[WikiPage, ...]],
    sessions: tuple[AgentSession, ...],
) -> str:
    title = CATEGORY_TITLES[category]
    sessions_by_id = {session.session_id: session for session in sessions}
    lines = [
        "---",
        "agentworkmemory_managed: true",
        "type: index",
        f"category: {category}",
        "---",
        f"# {title}",
        "",
        f"[[Home|Agent Work Memory]] · {len(pages)} page(s)",
        "",
        "## Pages",
        "",
    ]
    if not pages:
        lines.append("- No pages yet.")
    for page in sorted(pages, key=lambda item: item.title.casefold()):
        lines.append(f"- {page_link(page)}")
        sources = tuple(
            sessions_by_id[session_id]
            for session_id in page.source_session_ids
            if session_id in sessions_by_id
        )
        if sources:
            source_links = ", ".join(session_link(session) for session in sources)
            lines.append(f"  - Sources: {source_links}")
        incoming = backlinks.get(page.path, ())
        if incoming:
            incoming_links = ", ".join(page_link(source) for source in incoming)
            lines.append(f"  - Linked from: {incoming_links}")
        if page.tags:
            lines.append(f"  - Tags: {', '.join(page.tags)}")
    return "\n".join(lines).rstrip() + "\n"


def page_link(page: WikiPage) -> str:
    target = page.path.with_suffix("").as_posix()
    return f"[[{target}|{safe_alias(page.title)}]]"


def session_link(session: AgentSession) -> str:
    target = f"inbox/agent-sessions/{session.provider}-{session.session_id}"
    alias = safe_alias(f"{session.title} · {session.provider}")
    return f"[[{target}|{alias}]]"


def safe_alias(value: str) -> str:
    return " ".join(value.replace("|", " ").replace("[", " ").replace("]", " ").split())
