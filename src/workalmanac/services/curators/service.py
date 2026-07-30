from collections.abc import Sequence

from workalmanac.services.curators.models import (
    CuratorReadiness,
    CuratorRunRequest,
    CuratorRunResult,
)
from workalmanac.services.curators.ports import CuratorAdapter


class CuratorsService:
    def __init__(self, adapters: Sequence[CuratorAdapter] = ()):
        self.adapters = adapters_by_runtime(adapters)

    def check(self, runtime: str) -> CuratorReadiness:
        return self.adapter_for(runtime).check()

    def ensure_ready(self, runtime: str) -> CuratorReadiness:
        readiness = self.check(runtime)
        if readiness.available:
            return readiness
        repair = f" ({readiness.repair})" if readiness.repair else ""
        raise RuntimeError(
            f"curator {runtime} is unavailable: {readiness.message}{repair}"
        )

    def run(self, request: CuratorRunRequest) -> CuratorRunResult:
        return self.adapter_for(request.runtime).run(request)

    def adapter_for(self, runtime: str) -> CuratorAdapter:
        try:
            return self.adapters[runtime]
        except KeyError as error:
            choices = ", ".join(sorted(self.adapters)) or "none"
            raise ValueError(
                f"unknown curator runtime {runtime!r}; available: {choices}"
            ) from error


def adapters_by_runtime(
    adapters: Sequence[CuratorAdapter],
) -> dict[str, CuratorAdapter]:
    indexed: dict[str, CuratorAdapter] = {}
    for adapter in adapters:
        if adapter.runtime in indexed:
            raise ValueError(f"duplicate curator runtime: {adapter.runtime}")
        indexed[adapter.runtime] = adapter
    return indexed
