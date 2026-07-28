from datetime import UTC, datetime
from pathlib import Path

from agentworkmemory.database import open_database
from agentworkmemory.services.sessions.models import (
    AgentEvent,
    AgentEventKind,
    AgentSession,
    CollectorCursor,
    SessionState,
)


class SessionsStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def remember_session(self, session: AgentSession) -> AgentSession:
        with open_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO agent_sessions (
                  session_id, provider, provider_session_id, title, cwd,
                  source_path, started_at, ended_at, modified_at, state,
                  content_captured, distilled_at, distill_runtime, created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                  title = excluded.title,
                  cwd = excluded.cwd,
                  source_path = excluded.source_path,
                  started_at = COALESCE(agent_sessions.started_at, excluded.started_at),
                  ended_at = COALESCE(excluded.ended_at, agent_sessions.ended_at),
                  modified_at = excluded.modified_at,
                  state = excluded.state,
                  content_captured = MAX(
                    agent_sessions.content_captured,
                    excluded.content_captured
                  ),
                  distilled_at = agent_sessions.distilled_at,
                  distill_runtime = agent_sessions.distill_runtime,
                  updated_at = excluded.updated_at
                """,
                session_values(session),
            )
            connection.commit()
        remembered = self.get_session(session.session_id)
        if remembered is None:
            raise RuntimeError(f"failed to remember session {session.session_id}")
        return remembered

    def append_events(
        self,
        session_id: str,
        events: tuple[AgentEvent, ...],
        cursor: CollectorCursor,
    ) -> int:
        with open_database(self.database_path) as connection:
            before = connection.total_changes
            connection.executemany(
                """
                INSERT OR IGNORE INTO agent_events (
                  event_id, session_id, sequence, kind, role, label,
                  occurred_at, content, source_line, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tuple(event_values(event) for event in events),
            )
            inserted = connection.total_changes - before
            connection.execute(
                """
                INSERT INTO collector_cursors (
                  source_id, provider, source_path, last_line, size_bytes,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                  last_line = excluded.last_line,
                  size_bytes = excluded.size_bytes,
                  updated_at = excluded.updated_at
                """,
                (
                    cursor.source_id,
                    cursor.provider,
                    str(cursor.source_path),
                    cursor.last_line,
                    cursor.size_bytes,
                    cursor.updated_at.isoformat(),
                ),
            )
            connection.execute(
                """
                UPDATE agent_sessions
                SET content_captured = 1, updated_at = ?
                WHERE session_id = ?
                """,
                (datetime.now(UTC).isoformat(), session_id),
            )
            connection.commit()
        return inserted

    def get_session(self, session_id: str) -> AgentSession | None:
        with open_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM agent_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return session_from_row(row) if row is not None else None

    def list_sessions(self) -> tuple[AgentSession, ...]:
        with open_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM agent_sessions
                ORDER BY modified_at DESC, session_id
                """
            ).fetchall()
        return tuple(session_from_row(row) for row in rows)

    def events_for(self, session_id: str) -> tuple[AgentEvent, ...]:
        with open_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM agent_events
                WHERE session_id = ?
                ORDER BY sequence, source_line, event_id
                """,
                (session_id,),
            ).fetchall()
        return tuple(event_from_row(row) for row in rows)

    def cursor_for(self, source_id: str) -> CollectorCursor | None:
        with open_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM collector_cursors WHERE source_id = ?",
                (source_id,),
            ).fetchone()
        if row is None:
            return None
        return CollectorCursor(
            source_id=row["source_id"],
            provider=row["provider"],
            source_path=Path(row["source_path"]),
            last_line=row["last_line"],
            size_bytes=row["size_bytes"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def mark_distilled(
        self,
        session_ids: tuple[str, ...],
        *,
        runtime: str,
        distilled_at: datetime,
    ) -> None:
        with open_database(self.database_path) as connection:
            connection.executemany(
                """
                UPDATE agent_sessions
                SET distilled_at = ?, distill_runtime = ?, updated_at = ?
                WHERE session_id = ?
                """,
                tuple(
                    (
                        distilled_at.isoformat(),
                        runtime,
                        distilled_at.isoformat(),
                        session_id,
                    )
                    for session_id in session_ids
                ),
            )
            connection.commit()


def session_values(session: AgentSession) -> tuple[object, ...]:
    return (
        session.session_id,
        session.provider,
        session.provider_session_id,
        session.title,
        str(session.cwd) if session.cwd is not None else None,
        str(session.source_path) if session.source_path is not None else None,
        session.started_at.isoformat() if session.started_at is not None else None,
        session.ended_at.isoformat() if session.ended_at is not None else None,
        session.modified_at.isoformat(),
        session.state.value,
        int(session.content_captured),
        (
            session.distilled_at.isoformat()
            if session.distilled_at is not None
            else None
        ),
        session.distill_runtime,
        session.created_at.isoformat(),
        session.updated_at.isoformat(),
    )


def event_values(event: AgentEvent) -> tuple[object, ...]:
    return (
        event.event_id,
        event.session_id,
        event.sequence,
        event.kind.value,
        event.role,
        event.label,
        event.occurred_at.isoformat() if event.occurred_at is not None else None,
        event.content,
        event.source_line,
        event.created_at.isoformat(),
    )


def session_from_row(row: object) -> AgentSession:
    return AgentSession(
        session_id=row["session_id"],
        provider=row["provider"],
        provider_session_id=row["provider_session_id"],
        title=row["title"],
        cwd=Path(row["cwd"]) if row["cwd"] is not None else None,
        source_path=(
            Path(row["source_path"]) if row["source_path"] is not None else None
        ),
        started_at=(
            datetime.fromisoformat(row["started_at"])
            if row["started_at"] is not None
            else None
        ),
        ended_at=(
            datetime.fromisoformat(row["ended_at"])
            if row["ended_at"] is not None
            else None
        ),
        modified_at=datetime.fromisoformat(row["modified_at"]),
        state=SessionState(row["state"]),
        content_captured=bool(row["content_captured"]),
        distilled_at=(
            datetime.fromisoformat(row["distilled_at"])
            if row["distilled_at"] is not None
            else None
        ),
        distill_runtime=row["distill_runtime"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def event_from_row(row: object) -> AgentEvent:
    return AgentEvent(
        event_id=row["event_id"],
        session_id=row["session_id"],
        sequence=row["sequence"],
        kind=AgentEventKind(row["kind"]),
        role=row["role"],
        label=row["label"],
        occurred_at=(
            datetime.fromisoformat(row["occurred_at"])
            if row["occurred_at"] is not None
            else None
        ),
        content=row["content"],
        source_line=row["source_line"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
