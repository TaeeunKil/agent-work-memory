from workalmanac.database import open_database
from workalmanac.integrations.transcripts import (
    ClaudeTranscriptCollector,
    CodexTranscriptCollector,
)
from workalmanac.services.search import SearchService
from workalmanac.services.sessions import SessionsService
from workalmanac.services.sessions.store import SessionsStore
from workalmanac.services.vault import VaultService
from workalmanac.settings import WorkAlmanacConfig, load_config
from workalmanac.workflows.collect import CollectAgentRecordsWorkflow
from workalmanac.workflows.import_records import ImportAgentRecordsWorkflow


class WorkAlmanac:
    def __init__(
        self,
        *,
        sessions: SessionsService,
        vault: VaultService,
        collect: CollectAgentRecordsWorkflow,
        import_records: ImportAgentRecordsWorkflow,
        search: SearchService,
    ):
        self.sessions = sessions
        self.vault = vault
        self.collect = collect
        self.import_records = import_records
        self.search = search

    @property
    def config(self) -> WorkAlmanacConfig:
        return self.vault.config


def create_app(config: WorkAlmanacConfig | None = None) -> WorkAlmanac:
    resolved = config or load_config()
    with open_database(resolved.database_path):
        pass
    store = SessionsStore(resolved.database_path)
    sessions = SessionsService(store)
    vault = VaultService(resolved)
    collectors = (
        CodexTranscriptCollector(),
        ClaudeTranscriptCollector(),
    )
    collect = CollectAgentRecordsWorkflow(sessions, vault, collectors)
    import_records = ImportAgentRecordsWorkflow(sessions, vault)
    search = SearchService(resolved.database_path, sessions, vault)
    return WorkAlmanac(
        sessions=sessions,
        vault=vault,
        collect=collect,
        import_records=import_records,
        search=search,
    )
