import json
from pathlib import Path

from workalmanac.database import open_database
from workalmanac.services.synchronization.models import SyncReceipt, SyncStatus


class SynchronizationStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def remember(self, receipt: SyncReceipt) -> SyncReceipt:
        with open_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO sync_receipts (
                  run_id, providers, include_content, status,
                  sessions_discovered, sessions_updated, events_added,
                  error_type, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                  status = excluded.status,
                  sessions_discovered = excluded.sessions_discovered,
                  sessions_updated = excluded.sessions_updated,
                  events_added = excluded.events_added,
                  error_type = excluded.error_type,
                  finished_at = excluded.finished_at
                """,
                (
                    receipt.run_id,
                    json.dumps(receipt.providers),
                    int(receipt.include_content),
                    receipt.status.value,
                    receipt.sessions_discovered,
                    receipt.sessions_updated,
                    receipt.events_added,
                    receipt.error_type,
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
            raise RuntimeError(f"failed to remember sync run {receipt.run_id}")
        return remembered

    def get(self, run_id: str) -> SyncReceipt | None:
        with open_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM sync_receipts WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return sync_receipt_from_row(row) if row is not None else None

    def latest(self) -> SyncReceipt | None:
        with open_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM sync_receipts
                ORDER BY started_at DESC, run_id DESC
                LIMIT 1
                """
            ).fetchone()
        return sync_receipt_from_row(row) if row is not None else None

    def list(self, limit: int = 50) -> tuple[SyncReceipt, ...]:
        with open_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM sync_receipts
                ORDER BY started_at DESC, run_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(sync_receipt_from_row(row) for row in rows)


def sync_receipt_from_row(row: object) -> SyncReceipt:
    return SyncReceipt(
        run_id=row["run_id"],
        providers=tuple(json.loads(row["providers"])),
        include_content=bool(row["include_content"]),
        status=SyncStatus(row["status"]),
        sessions_discovered=row["sessions_discovered"],
        sessions_updated=row["sessions_updated"],
        events_added=row["events_added"],
        error_type=row["error_type"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )
