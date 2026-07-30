from collections.abc import Callable
from hashlib import sha256

from agentworkmemory.integrations.transcripts.models import (
    DiscoveredAgentSession,
    TranscriptCollector,
)
from agentworkmemory.services.sessions.distillation import is_internal_workspace
from agentworkmemory.services.sessions.models import CollectorCursor
from agentworkmemory.services.sessions.service import SessionsService
from agentworkmemory.services.vault.service import VaultService
from agentworkmemory.services.wiki.service import WikiCatalogService
from agentworkmemory.workflows.collect.models import (
    CollectAgentRecords,
    CollectionReceipt,
)


class CollectAgentRecordsWorkflow:
    def __init__(
        self,
        sessions: SessionsService,
        vault: VaultService,
        wiki: WikiCatalogService,
        collectors: tuple[TranscriptCollector, ...],
    ):
        self.sessions = sessions
        self.vault = vault
        self.wiki = wiki
        self.collectors = {collector.provider: collector for collector in collectors}

    def collect(
        self,
        request: CollectAgentRecords,
        progress: Callable[[str], None] | None = None,
    ) -> CollectionReceipt:
        discovered_count = 0
        updated_count = 0
        events_added = 0
        session_ids: list[str] = []
        for provider in request.providers:
            if progress is not None:
                progress(f"Scanning {provider} transcripts.")
            collector = self.collectors.get(provider)
            if collector is None:
                raise ValueError(f"no transcript collector for {provider}")
            provider_discovered = 0
            provider_events = 0
            provider_internal = 0
            for discovered in collector.discover(request.home):
                if is_internal_workspace(
                    discovered.cwd,
                    self.vault.config.state_dir,
                ):
                    provider_internal += 1
                    continue
                discovered_count += 1
                provider_discovered += 1
                session = self.sessions.remember_discovered(
                    provider=discovered.provider,
                    provider_session_id=discovered.provider_session_id,
                    cwd=discovered.cwd,
                    source_path=discovered.source_path,
                    modified_at=discovered.modified_at,
                    started_at=discovered.started_at,
                )
                session_ids.append(session.session_id)
                if request.include_content:
                    source_id = stable_source_id(discovered)
                    cursor = self.sessions.cursor_for(source_id)
                    after_line = 0 if cursor is None else cursor.last_line
                    if cursor is not None and discovered.size_bytes < cursor.size_bytes:
                        after_line = 0
                    read = collector.read(
                        discovered,
                        work_session_id=session.session_id,
                        after_line=after_line,
                    )
                    inserted = self.sessions.append_events(
                        session.session_id,
                        read.events,
                        CollectorCursor(
                            source_id=source_id,
                            provider=provider,
                            source_path=discovered.source_path,
                            last_line=read.last_line,
                            size_bytes=read.size_bytes,
                            updated_at=discovered.modified_at,
                        ),
                    )
                    events_added += inserted
                    provider_events += inserted
                    if inserted > 0 or not session.content_captured:
                        updated_count += 1
                self.vault.refresh_session(
                    self.sessions.get(session.session_id),
                    self.sessions.events(session.session_id),
                )
            if progress is not None:
                internal_summary = (
                    f", {provider_internal} internal session(s) excluded"
                    if provider_internal
                    else ""
                )
                progress(
                    f"{provider} transcripts complete: "
                    f"{provider_discovered} session(s), "
                    f"{provider_events} new event(s)"
                    f"{internal_summary}."
                )
        self.wiki.refresh()
        return CollectionReceipt(
            sessions_discovered=discovered_count,
            sessions_updated=updated_count,
            events_added=events_added,
            session_ids=tuple(dict.fromkeys(session_ids)),
        )


def stable_source_id(discovered: DiscoveredAgentSession) -> str:
    identity = (
        f"{discovered.provider}\0"
        f"{discovered.provider_session_id}\0{discovered.source_path}"
    )
    return f"src_{sha256(identity.encode()).hexdigest()[:24]}"


def combine_collection_receipts(
    receipts: tuple[CollectionReceipt, ...],
) -> CollectionReceipt:
    return CollectionReceipt(
        sessions_discovered=sum(item.sessions_discovered for item in receipts),
        sessions_updated=sum(item.sessions_updated for item in receipts),
        events_added=sum(item.events_added for item in receipts),
        session_ids=tuple(
            dict.fromkeys(
                session_id
                for item in receipts
                for session_id in item.session_ids
            )
        ),
    )
