from datetime import UTC, datetime

from agentworkmemory.services.curators.models import (
    CuratorRunRequest,
    CuratorRunStatus,
)
from agentworkmemory.services.curators.service import CuratorsService
from agentworkmemory.services.distillation.models import (
    DistillReceipt,
    DistillStatus,
)
from agentworkmemory.services.distillation.outcomes import (
    classify_session_outcomes,
    summarize_session_outcomes,
)
from agentworkmemory.services.distillation.service import DistillationService
from agentworkmemory.services.search.service import SearchService
from agentworkmemory.services.sessions.service import SessionsService
from agentworkmemory.services.vault.service import VaultService
from agentworkmemory.services.wiki.service import WikiCatalogService
from agentworkmemory.workflows.distill.models import DistillSessions
from agentworkmemory.workflows.distill.prompt import distill_prompt


class DistillSessionsWorkflow:
    def __init__(
        self,
        sessions: SessionsService,
        curators: CuratorsService,
        distillation: DistillationService,
        vault: VaultService,
        search: SearchService,
        wiki: WikiCatalogService,
    ):
        self.sessions = sessions
        self.curators = curators
        self.distillation = distillation
        self.vault = vault
        self.search = search
        self.wiki = wiki

    def preflight(self, request: DistillSessions) -> None:
        selected = tuple(
            (self.sessions.get(session_id), self.sessions.events(session_id))
            for session_id in request.session_ids
        )
        distill_prompt(selected, request.content_access)
        self.curators.ensure_ready(request.runtime)
        self.vault.validate_curator_source()

    def run(self, request: DistillSessions) -> DistillReceipt:
        selected = tuple(
            (self.sessions.get(session_id), self.sessions.events(session_id))
            for session_id in request.session_ids
        )
        prompt = distill_prompt(selected, request.content_access)
        receipt = self.distillation.begin(
            runtime=request.runtime,
            model=request.model,
            content_access=request.content_access,
            session_ids=request.session_ids,
        )
        original_snapshot = None
        changed = ()
        outcomes = ()
        before_pages = self.wiki.pages()
        try:
            self.curators.ensure_ready(request.runtime)
            with self.vault.curator_workspace() as (
                workspace,
                snapshot,
                original_snapshot,
            ):
                result = self.curators.run(
                    CuratorRunRequest(
                        runtime=request.runtime,
                        model=request.model,
                        vault_path=workspace,
                        prompt=prompt,
                        content_access=request.content_access,
                    )
                )
                if result.status is not CuratorRunStatus.SUCCEEDED:
                    raise RuntimeError(
                        f"curator {request.runtime} ended with "
                        f"{result.status.value}: {first_line(result.output_text)}"
                    )
                self.vault.normalize_curator_workspace_permissions(workspace)
                changed = self.vault.validate_distill_changes(snapshot)
                self.vault.apply_distill_changes(workspace, changed)
            outcomes = classify_session_outcomes(
                request.session_ids,
                before=before_pages,
                after=self.wiki.pages(),
                changed_files=changed,
            )
            distilled_at = datetime.now(UTC)
            for session, events in selected:
                projected = session.model_copy(
                    update={
                        "distilled_at": distilled_at,
                        "distill_runtime": request.runtime,
                    }
                )
                self.vault.refresh_session(projected, events)
            self.wiki.refresh()
            self.search.refresh()
            self.sessions.mark_distilled(
                request.session_ids,
                runtime=request.runtime,
                distilled_at=distilled_at,
            )
        except Exception as error:
            if original_snapshot is not None:
                original_snapshot.restore()
            self.distillation.finish(
                receipt,
                status=DistillStatus.FAILED,
                changed_files=(),
                output_summary=type(error).__name__,
            )
            raise
        return self.distillation.finish(
            receipt,
            status=DistillStatus.SUCCEEDED,
            changed_files=changed,
            session_outcomes=outcomes,
            output_summary=(
                f"{request.runtime} completed; {len(changed)} durable file(s) "
                f"changed; {summarize_session_outcomes(outcomes)}"
            ),
        )


def first_line(value: str) -> str:
    lines = value.splitlines()
    return lines[0] if lines else value
