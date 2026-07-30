import json
from pathlib import Path

from agentworkmemory.database import open_database
from agentworkmemory.services.curators.models import ContentAccess
from agentworkmemory.services.distillation.models import (
    DistillReceipt,
    DistillStatus,
)


class DistillationStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def remember(self, receipt: DistillReceipt) -> DistillReceipt:
        with open_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO distill_receipts (
                  run_id, runtime, model, content_access, session_ids, status,
                  changed_files, output_summary, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                  status = excluded.status,
                  changed_files = excluded.changed_files,
                  output_summary = excluded.output_summary,
                  finished_at = excluded.finished_at
                """,
                (
                    receipt.run_id,
                    receipt.runtime,
                    receipt.model,
                    receipt.content_access.value,
                    json.dumps(receipt.session_ids),
                    receipt.status.value,
                    json.dumps(
                        tuple(path.as_posix() for path in receipt.changed_files)
                    ),
                    receipt.output_summary,
                    receipt.started_at.isoformat(),
                    (
                        receipt.finished_at.isoformat()
                        if receipt.finished_at is not None
                        else None
                    ),
                ),
            )
            connection.commit()
        remembered = self.get(receipt.run_id)
        if remembered is None:
            raise RuntimeError(f"failed to remember distill run {receipt.run_id}")
        return remembered

    def get(self, run_id: str) -> DistillReceipt | None:
        with open_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM distill_receipts WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return DistillReceipt(
            run_id=row["run_id"],
            runtime=row["runtime"],
            model=row["model"],
            content_access=ContentAccess(row["content_access"]),
            session_ids=tuple(json.loads(row["session_ids"])),
            status=DistillStatus(row["status"]),
            changed_files=tuple(
                Path(value) for value in json.loads(row["changed_files"])
            ),
            output_summary=row["output_summary"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    def list(self, limit: int = 50) -> tuple[DistillReceipt, ...]:
        with open_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT run_id FROM distill_receipts
                ORDER BY started_at DESC, run_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        receipts: list[DistillReceipt] = []
        for row in rows:
            receipt = self.get(row["run_id"])
            if receipt is not None:
                receipts.append(receipt)
        return tuple(receipts)
