from pathlib import Path

from agentworkmemory.core import AgentWorkMemoryModel


class WikiPage(AgentWorkMemoryModel):
    path: Path
    title: str
    category: str
    short_title_ko: str | None = None
    short_title_en: str | None = None
    tags: tuple[str, ...] = ()
    source_session_ids: tuple[str, ...] = ()
    outgoing_links: tuple[Path, ...] = ()


class WikiPageLink(AgentWorkMemoryModel):
    source_path: Path
    target_path: Path
