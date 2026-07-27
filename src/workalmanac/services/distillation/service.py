from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from workalmanac.services.curators.models import ContentAccess
from workalmanac.services.distillation.models import (
    DistillReceipt,
    DistillStatus,
)
from workalmanac.services.distillation.store import DistillationStore

MAX_OUTPUT_SUMMARY_CHARS = 2_000


class DistillationService:
    def __init__(self, store: DistillationStore):
        self.store = store

    def begin(
        self,
        *,
        runtime: str,
        model: str | None,
        content_access: ContentAccess,
        session_ids: tuple[str, ...],
    ) -> DistillReceipt:
        return self.store.remember(
            DistillReceipt(
                run_id=f"dst_{uuid4().hex}",
                runtime=runtime,
                model=model,
                content_access=content_access,
                session_ids=session_ids,
                status=DistillStatus.RUNNING,
                started_at=datetime.now(UTC),
            )
        )

    def finish(
        self,
        receipt: DistillReceipt,
        *,
        status: DistillStatus,
        changed_files: tuple[Path, ...] = (),
        output_summary: str | None = None,
    ) -> DistillReceipt:
        summary = output_summary.strip() if output_summary else None
        if summary is not None:
            summary = summary[:MAX_OUTPUT_SUMMARY_CHARS]
        return self.store.remember(
            receipt.model_copy(
                update={
                    "status": status,
                    "changed_files": changed_files,
                    "output_summary": summary,
                    "finished_at": datetime.now(UTC),
                }
            )
        )

    def get(self, run_id: str) -> DistillReceipt | None:
        return self.store.get(run_id)
