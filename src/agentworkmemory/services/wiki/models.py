from pathlib import Path

from agentworkmemory.core import AgentWorkMemoryModel


class WikiPage(AgentWorkMemoryModel):
    path: Path
    title: str
    category: str
    tags: tuple[str, ...] = ()
    source_session_ids: tuple[str, ...] = ()
    outgoing_links: tuple[Path, ...] = ()
