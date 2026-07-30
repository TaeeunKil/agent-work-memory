from pathlib import Path
from typing import Protocol

from agentworkmemory.services.remotes.models import (
    RemoteHost,
    RemoteManifest,
    RemoteSnapshot,
)


class RemoteSnapshotAdapter(Protocol):
    def snapshot(
        self,
        host: RemoteHost,
        previous: RemoteManifest,
        cache_root: Path,
    ) -> RemoteSnapshot: ...
