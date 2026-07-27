from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from workalmanac.core import WorkAlmanacModel
from workalmanac.integrations.record_bundle import load_record_bundle
from workalmanac.services.sessions.models import AgentEvent, CollectorCursor
from workalmanac.services.sessions.service import (
    SessionsService,
    stable_event_id,
)
from workalmanac.services.vault.service import VaultService


class ImportAgentRecordResult(WorkAlmanacModel):
    session_id: str
    events_added: int
    wiki_path: Path


class ImportAgentRecordsWorkflow:
    def __init__(self, sessions: SessionsService, vault: VaultService):
        self.sessions = sessions
        self.vault = vault

    def import_file(self, path: Path) -> ImportAgentRecordResult:
        source_path = path.expanduser().resolve()
        bundle = load_record_bundle(source_path)
        stat = source_path.stat()
        observed_at = datetime.fromtimestamp(stat.st_mtime, UTC)
        session = self.sessions.remember_discovered(
            provider=bundle.provider,
            provider_session_id=bundle.session_id,
            cwd=bundle.cwd,
            source_path=source_path,
            modified_at=observed_at,
            started_at=bundle.started_at,
            title=bundle.title,
            ended_at=bundle.ended_at,
        )
        events = tuple(
            AgentEvent(
                event_id=stable_event_id(
                    session_id=session.session_id,
                    source_line=index,
                    kind=event.kind,
                    content=event.content,
                ),
                session_id=session.session_id,
                sequence=index,
                kind=event.kind,
                role=event.role,
                label=event.label or event.role or event.kind.value,
                occurred_at=event.occurred_at,
                content=event.content,
                source_line=index,
                created_at=observed_at,
            )
            for index, event in enumerate(bundle.events, start=1)
        )
        source_id = bundle_source_id(bundle.provider, bundle.session_id, source_path)
        inserted = self.sessions.append_events(
            session.session_id,
            events,
            CollectorCursor(
                source_id=source_id,
                provider=bundle.provider,
                source_path=source_path,
                last_line=len(events),
                size_bytes=stat.st_size,
                updated_at=observed_at,
            ),
        )
        remembered = self.sessions.get(session.session_id)
        page = self.vault.refresh_session(
            remembered,
            self.sessions.events(remembered.session_id),
        )
        return ImportAgentRecordResult(
            session_id=remembered.session_id,
            events_added=inserted,
            wiki_path=page,
        )


def bundle_source_id(provider: str, session_id: str, path: Path) -> str:
    identity = f"{provider}\0{session_id}\0{path}"
    return f"src_{sha256(identity.encode()).hexdigest()[:24]}"
