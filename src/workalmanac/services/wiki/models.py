from pathlib import Path

from workalmanac.core import WorkAlmanacModel


class WikiPage(WorkAlmanacModel):
    path: Path
    title: str
    category: str
    tags: tuple[str, ...] = ()
    source_session_ids: tuple[str, ...] = ()
    outgoing_links: tuple[Path, ...] = ()
