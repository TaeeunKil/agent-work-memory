from enum import StrEnum
from pathlib import Path

from agentworkmemory.core import AgentWorkMemoryModel


class Locale(StrEnum):
    KO = "ko"
    EN = "en"


class TranslationStatus(StrEnum):
    ORIGINAL = "original"
    CURRENT = "current"
    STALE = "stale"
    MISSING = "missing"
    INVALID = "invalid"


class PageRepresentation(AgentWorkMemoryModel):
    canonical_path: Path
    requested_locale: Locale
    resolved_locale: Locale
    original_locale: Locale
    status: TranslationStatus
    title: str
    body: str
