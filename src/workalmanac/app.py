from collections.abc import Sequence

from workalmanac.database import open_database
from workalmanac.integrations.automation import default_scheduler_adapter
from workalmanac.integrations.curators import (
    OllamaCuratorAdapter,
    YokeCuratorAdapter,
)
from workalmanac.integrations.transcripts import (
    ClaudeTranscriptCollector,
    CodexTranscriptCollector,
)
from workalmanac.services.automation.ports import SchedulerAdapter
from workalmanac.services.automation.service import AutomationService
from workalmanac.services.automation.store import AutomationStore
from workalmanac.services.curators.ports import CuratorAdapter
from workalmanac.services.curators.service import CuratorsService
from workalmanac.services.distillation.service import DistillationService
from workalmanac.services.distillation.store import DistillationStore
from workalmanac.services.search import SearchService
from workalmanac.services.sessions import SessionsService
from workalmanac.services.sessions.store import SessionsStore
from workalmanac.services.synchronization.service import SynchronizationService
from workalmanac.services.synchronization.store import SynchronizationStore
from workalmanac.services.vault import VaultService
from workalmanac.services.viewer import ViewerService
from workalmanac.services.wiki import WikiCatalogService
from workalmanac.settings import WorkAlmanacConfig, load_config
from workalmanac.workflows.collect import CollectAgentRecordsWorkflow
from workalmanac.workflows.distill import DistillSessionsWorkflow
from workalmanac.workflows.import_records import ImportAgentRecordsWorkflow
from workalmanac.workflows.sync import SyncAgentRecordsWorkflow


class WorkAlmanac:
    def __init__(
        self,
        *,
        automation: AutomationService,
        sessions: SessionsService,
        vault: VaultService,
        collect: CollectAgentRecordsWorkflow,
        curators: CuratorsService,
        distill: DistillSessionsWorkflow,
        distillation: DistillationService,
        import_records: ImportAgentRecordsWorkflow,
        search: SearchService,
        sync: SyncAgentRecordsWorkflow,
        synchronization: SynchronizationService,
        viewer: ViewerService,
        wiki: WikiCatalogService,
    ):
        self.automation = automation
        self.sessions = sessions
        self.vault = vault
        self.collect = collect
        self.curators = curators
        self.distill = distill
        self.distillation = distillation
        self.import_records = import_records
        self.search = search
        self.sync = sync
        self.synchronization = synchronization
        self.viewer = viewer
        self.wiki = wiki

    @property
    def config(self) -> WorkAlmanacConfig:
        return self.vault.config


def create_app(
    config: WorkAlmanacConfig | None = None,
    *,
    curator_adapters: Sequence[CuratorAdapter] | None = None,
    scheduler_adapter: SchedulerAdapter | None = None,
    ollama_url: str | None = None,
) -> WorkAlmanac:
    resolved = config or load_config()
    with open_database(resolved.database_path):
        pass
    store = SessionsStore(resolved.database_path)
    sessions = SessionsService(store)
    vault = VaultService(resolved)
    wiki = WikiCatalogService(vault, sessions)
    collectors = (
        CodexTranscriptCollector(),
        ClaudeTranscriptCollector(),
    )
    collect = CollectAgentRecordsWorkflow(sessions, vault, wiki, collectors)
    import_records = ImportAgentRecordsWorkflow(sessions, vault, wiki)
    search = SearchService(resolved.database_path, sessions, vault)
    synchronization = SynchronizationService(
        SynchronizationStore(resolved.database_path)
    )
    viewer = ViewerService(sessions, vault, wiki, synchronization)
    sync = SyncAgentRecordsWorkflow(
        collect,
        search,
        synchronization,
        resolved.state_dir / "sync.lock",
    )
    automation = AutomationService(
        scheduler_adapter or default_scheduler_adapter(),
        AutomationStore(resolved.state_dir / "auto-sync.json"),
        resolved.state_dir,
    )
    adapters = (
        tuple(curator_adapters)
        if curator_adapters is not None
        else (
            YokeCuratorAdapter(
                "codex",
                resolved.state_dir / "curators" / "codex",
            ),
            YokeCuratorAdapter(
                "claude",
                resolved.state_dir / "curators" / "claude",
            ),
            OllamaCuratorAdapter(
                ollama_url if ollama_url is not None else "http://127.0.0.1:11434"
            ),
        )
    )
    curators = CuratorsService(adapters)
    distillation = DistillationService(DistillationStore(resolved.database_path))
    distill = DistillSessionsWorkflow(
        sessions,
        curators,
        distillation,
        vault,
        search,
        wiki,
    )
    return WorkAlmanac(
        automation=automation,
        sessions=sessions,
        vault=vault,
        collect=collect,
        curators=curators,
        distill=distill,
        distillation=distillation,
        import_records=import_records,
        search=search,
        sync=sync,
        synchronization=synchronization,
        viewer=viewer,
        wiki=wiki,
    )
