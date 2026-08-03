from pathlib import Path

from pydantic import field_validator

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.curators.models import ContentAccess
from agentworkmemory.services.translations import Locale


class TranslateWikiPages(AgentWorkMemoryModel):
    paths: tuple[Path, ...]
    locale: Locale
    runtime: str
    model: str | None = None
    content_access: ContentAccess

    @field_validator("paths")
    @classmethod
    def require_paths(cls, value: tuple[Path, ...]) -> tuple[Path, ...]:
        paths = tuple(dict.fromkeys(value))
        if not paths:
            raise ValueError("translation requires at least one Wiki page")
        if len(paths) > 20:
            raise ValueError("translation accepts at most 20 Wiki pages per run")
        return paths

    @field_validator("runtime")
    @classmethod
    def require_runtime(cls, value: str) -> str:
        runtime = value.strip()
        if not runtime:
            raise ValueError("translation runtime must not be empty")
        return runtime

    @field_validator("content_access")
    @classmethod
    def require_content_access(cls, value: ContentAccess) -> ContentAccess:
        if value is ContentAccess.METADATA_ONLY:
            raise ValueError("translation requires access to the selected Wiki body")
        return value
