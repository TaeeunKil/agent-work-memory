from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath

from pydantic import Field, field_validator, model_validator

from agentworkmemory.core import AgentWorkMemoryModel
from agentworkmemory.services.sessions.models import (
    AgentProvider,
    AgentProviderId,
)


class RemoteHost(AgentWorkMemoryModel):
    target: str
    providers: tuple[AgentProviderId, ...]
    added_at: datetime

    @field_validator("target")
    @classmethod
    def valid_target(cls, value: str) -> str:
        return validate_remote_target(value)

    @field_validator("providers")
    @classmethod
    def supported_providers(
        cls,
        value: tuple[AgentProviderId, ...],
    ) -> tuple[AgentProviderId, ...]:
        providers = tuple(dict.fromkeys(value))
        allowed = {AgentProvider.CODEX, AgentProvider.CLAUDE}
        if not providers or any(provider not in allowed for provider in providers):
            raise ValueError("remote providers must be codex or claude")
        return providers


class RemoteFileObservation(AgentWorkMemoryModel):
    path: str
    provider: AgentProviderId
    size_bytes: int = Field(ge=0)
    modified_ns: int = Field(ge=0)

    @field_validator("path")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        normalized = value.strip().replace("\\", "/")
        relative = PurePosixPath(normalized)
        if (
            not normalized
            or normalized.startswith("/")
            or relative.is_absolute()
            or ".." in relative.parts
            or ":" in normalized
            or "\0" in normalized
            or relative.suffix.lower() != ".jsonl"
        ):
            raise ValueError("remote transcript path is unsafe")
        return relative.as_posix()

    @model_validator(mode="after")
    def provider_path_matches(self) -> "RemoteFileObservation":
        prefixes = {
            AgentProvider.CODEX: ".codex/sessions/",
            AgentProvider.CLAUDE: ".claude/projects/",
        }
        prefix = prefixes.get(self.provider)
        if prefix is None or not self.path.startswith(prefix):
            raise ValueError("remote transcript path does not match its provider")
        return self


class RemoteManifest(AgentWorkMemoryModel):
    files: tuple[RemoteFileObservation, ...] = ()


class RemoteSnapshot(AgentWorkMemoryModel):
    local_home: Path
    manifest: RemoteManifest
    files_downloaded: int
    bytes_downloaded: int


class RemoteSyncState(StrEnum):
    NEVER = "never"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RemoteSyncStatus(AgentWorkMemoryModel):
    target: str
    state: RemoteSyncState = RemoteSyncState.NEVER
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    files_observed: int = 0
    files_downloaded: int = 0
    bytes_downloaded: int = 0
    error_type: str | None = None


class RemoteOverview(AgentWorkMemoryModel):
    host: RemoteHost
    status: RemoteSyncStatus


class RemoteRegistry(AgentWorkMemoryModel):
    hosts: tuple[RemoteHost, ...] = ()


class RemoteStatusLedger(AgentWorkMemoryModel):
    statuses: tuple[RemoteSyncStatus, ...] = ()


def validate_remote_target(value: str) -> str:
    target = value.strip()
    allowed = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789._-@"
    )
    if (
        not target
        or target.startswith("-")
        or len(target) > 255
        or target.count("@") > 1
        or any(character.isspace() for character in target)
        or any(character not in allowed for character in target)
        or "*" in target
        or "?" in target
    ):
        raise ValueError("SSH host must be a concrete host or config alias")
    parts = target.split("@")
    if any(not part or part.startswith("-") for part in parts):
        raise ValueError("SSH host must be a concrete host or config alias")
    return target
