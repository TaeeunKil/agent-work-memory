from pathlib import Path
from typing import Protocol

from agentworkmemory.services.improvement.models import (
    EvaluationCaseResult,
    ImprovementCandidate,
    ImprovementRun,
)


class RepositoryRevisionReader(Protocol):
    def head(self, repository: Path) -> str: ...


class ImprovementEvaluator(Protocol):
    def compare(
        self,
        run: ImprovementRun,
        candidate: ImprovementCandidate,
    ) -> tuple[EvaluationCaseResult, ...]: ...
