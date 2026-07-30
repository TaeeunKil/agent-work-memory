from typing import Protocol

from agentworkmemory.services.curators.models import (
    CuratorReadiness,
    CuratorRunRequest,
    CuratorRunResult,
)


class CuratorAdapter(Protocol):
    runtime: str

    def check(self) -> CuratorReadiness: ...

    def run(self, request: CuratorRunRequest) -> CuratorRunResult: ...
