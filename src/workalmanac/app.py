from collections.abc import Sequence

from workalmanac.database import open_database
from workalmanac.integrations.auto_distillation import (
    default_auto_distill_scheduler_adapter,
)
from workalmanac.integrations.automation import default_scheduler_adapter
from workalmanac.integrations.curators import (
    OllamaCuratorAdapter,
    YokeCuratorAdapter,
)
from workalmanac.integrations.remotes import SshRemoteSnapshotAdapter
from workalmanac.integrations.transcripts import (
    ClaudeTranscriptCollector,
    CodexTranscriptCollector,
)
from workalmanac.services.auto_distillation.ports import (
    AutoDistillSchedulerAdapter,
)
from workalmanac.services.auto_distillation.service import (
    AutoDistillationService,
)
from workalmanac.services.auto_distillation.store import AutoDistillStore
from workalmanac.services.automation.ports import SchedulerAdapter
from workalmanac.services.automation.service import AutomationService
from workalmanac.services.automation.store import AutomationStore
from workalmanac.services.curators.ports import CuratorAdapter
from workalmanac.services.curators.service import CuratorsService
from workalmanac.services.diagnostics import DiagnosticsService
from workalmanac.services.distillation.service import DistillationService
from workalmanac.services.distillation.store import DistillationStore
from workalmanac.services.remotes.ports import RemoteSnapshotAdapter
from workalmanac.services.remotes.service import RemotesService
from workalmanac.services.remotes.store import RemoteStore
from workalmanac.services.search import SearchService
from workalmanac.services.sessions import SessionsService
from workalmanac.services.sessions.store import SessionsStore
from workalmanac.services.synchronization.service import SynchronizationService
from workalmanac.services.synchronization.store import SynchronizationStore
from workalmanac.services.vault import VaultService
from workalmanac.services.viewer import ViewerService
from workalmanac.services.wiki import WikiCatalogService
from workalmanac.settings import WorkAlmanacConfig, load_config
from workalmanac.workflows.auto_distill import AutoDistillWorkflow
from workalmanac.workflows.collect import CollectAgentRecordsWorkflow
from workalmanac.workflows.distill import DistillSessionsWorkflow
from workalmanac.workflows.import_legacy import ImportLegacyAlmanacWorkflow
from workalmanac.workflows.import_records import ImportAgentRecordsWorkflow
from workalmanac.workflows.remote_sync import SyncRemoteRecordsWorkflow
from workalmanac.workflows.setup import SetupWorkAlmanacWorkflow
from workalmanac.workflows.sync import SyncAgentRecordsWorkflow


class WorkAlmanac:
    def __init__(
        self,
        *,
        automation: AutomationService,
        auto_distillation: AutoDistillationService,
        auto_distill: AutoDistillWorkflow,
        sessions: SessionsService,
        vault: VaultService,
        collect: CollectAgentRecordsWorkflow,
        curators: CuratorsService,
        diagnostics: DiagnosticsService,
        distill: DistillSessionsWorkflow,
        distillation: DistillationService,
        import_records: ImportAgentRecordsWorkflow,
        import_legacy: ImportLegacyAlmanacWorkflow,
        remotes: RemotesService,
        remote_sync: SyncRemoteRecordsWorkflow,
        search: SearchService,
        setup: SetupWorkAlmanacWorkflow,
        sync: SyncAgentRecordsWorkflow,
        synchronization: SynchronizationService,
        viewer: ViewerService,
        wiki: WikiCatalogService,
    ):
        self.automation = automation
        self.auto_distillation = auto_distillation
        self.auto_distill = auto_distill
        self.sessions = sessions
        self.vault = vault
        self.collect = collect
        self.curators = curators
        self.diagnostics = diagnostics
        self.distill = distill
        self.distillation = distillation
        self.import_records = import_records
        self.import_legacy = import_legacy
        self.remotes = remotes
        self.remote_sync = remote_sync
        self.search = search
        self.setup = setup
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
    auto_distill_scheduler_adapter: AutoDistillSchedulerAdapter | None = None,
    remote_adapter: RemoteSnapshotAdapter | None = None,
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
    remotes = RemotesService(
        RemoteStore(resolved.state_dir / "remotes"),
        remote_adapter or SshRemoteSnapshotAdapter(),
    )
    remote_sync = SyncRemoteRecordsWorkflow(remotes, collect)
    import_records = ImportAgentRecordsWorkflow(sessions, vault, wiki)
    search = SearchService(resolved.database_path, sessions, vault)
    import_legacy = ImportLegacyAlmanacWorkflow(vault, wiki, search)
    synchronization = SynchronizationService(
        SynchronizationStore(resolved.database_path)
    )
    viewer = ViewerService(sessions, vault, wiki, synchronization)
    sync = SyncAgentRecordsWorkflow(
        collect,
        remote_sync,
        search,
        synchronization,
        resolved.state_dir / "sync.lock",
    )
    automation = AutomationService(
        scheduler_adapter or default_scheduler_adapter(),
        AutomationStore(resolved.state_dir / "auto-sync.json"),
        resolved.state_dir,
    )
    auto_distillation = AutoDistillationService(
        auto_distill_scheduler_adapter
        or default_auto_distill_scheduler_adapter(),
        AutoDistillStore(resolved.state_dir / "auto-distill.json"),
        resolved.state_dir,
    )
    setup = SetupWorkAlmanacWorkflow(vault, wiki, sync, automation)
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
    diagnostics = DiagnosticsService(
        resolved,
        vault,
        automation,
        auto_distillation,
        curators,
        sessions,
        wiki,
        remotes,
    )
    distillation = DistillationService(DistillationStore(resolved.database_path))
    distill = DistillSessionsWorkflow(
        sessions,
        curators,
        distillation,
        vault,
        search,
        wiki,
    )
    auto_distill = AutoDistillWorkflow(
        auto_distillation,
        sessions,
        distill,
        resolved.state_dir / "auto-distill.lock",
    )
    return WorkAlmanac(
        automation=automation,
        auto_distillation=auto_distillation,
        auto_distill=auto_distill,
        sessions=sessions,
        vault=vault,
        collect=collect,
        curators=curators,
        diagnostics=diagnostics,
        distill=distill,
        distillation=distillation,
        import_records=import_records,
        import_legacy=import_legacy,
        remotes=remotes,
        remote_sync=remote_sync,
        search=search,
        setup=setup,
        sync=sync,
        synchronization=synchronization,
        viewer=viewer,
        wiki=wiki,
    )
