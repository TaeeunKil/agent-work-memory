from datetime import UTC, datetime

from workalmanac.services.curators.models import (
    CuratorRunRequest,
    CuratorRunStatus,
)
from workalmanac.services.curators.service import CuratorsService
from workalmanac.services.distillation.models import (
    DistillReceipt,
    DistillStatus,
)
from workalmanac.services.distillation.service import DistillationService
from workalmanac.services.search.service import SearchService
from workalmanac.services.sessions.service import SessionsService
from workalmanac.services.vault.service import VaultService
from workalmanac.services.wiki.service import WikiCatalogService
from workalmanac.workflows.distill.models import DistillSessions
from workalmanac.workflows.distill.prompt import distill_prompt


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
                changed = self.vault.validate_distill_changes(snapshot)
                self.vault.apply_distill_changes(workspace, changed)
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
            output_summary=(
                f"{request.runtime} completed; {len(changed)} durable file(s) changed"
            ),
        )


def first_line(value: str) -> str:
    lines = value.splitlines()
    return lines[0] if lines else value
