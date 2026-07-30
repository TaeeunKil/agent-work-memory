from collections.abc import Sequence

from workalmanac.database import open_database
from workalmanac.integrations.curators import YokeCuratorAdapter
from workalmanac.integrations.transcripts import (
    ClaudeTranscriptCollector,
    CodexTranscriptCollector,
)
from workalmanac.services.curators.ports import CuratorAdapter
from workalmanac.services.curators.service import CuratorsService
from workalmanac.services.distillation.service import DistillationService
from workalmanac.services.distillation.store import DistillationStore
from workalmanac.services.search import SearchService
from workalmanac.services.sessions import SessionsService
from workalmanac.services.sessions.store import SessionsStore
from workalmanac.services.vault import VaultService
from workalmanac.settings import WorkAlmanacConfig, load_config
from workalmanac.workflows.collect import CollectAgentRecordsWorkflow
from workalmanac.workflows.distill import DistillSessionsWorkflow
from workalmanac.workflows.import_records import ImportAgentRecordsWorkflow


class WorkAlmanac:
    def __init__(
        self,
        *,
        sessions: SessionsService,
        vault: VaultService,
        collect: CollectAgentRecordsWorkflow,
        curators: CuratorsService,
        distill: DistillSessionsWorkflow,
        distillation: DistillationService,
        import_records: ImportAgentRecordsWorkflow,
        search: SearchService,
    ):
        self.sessions = sessions
        self.vault = vault
        self.collect = collect
        self.curators = curators
        self.distill = distill
        self.distillation = distillation
        self.import_records = import_records
        self.search = search

    @property
    def config(self) -> WorkAlmanacConfig:
        return self.vault.config


def create_app(
    config: WorkAlmanacConfig | None = None,
    *,
    curator_adapters: Sequence[CuratorAdapter] | None = None,
) -> WorkAlmanac:
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
    )
    return WorkAlmanac(
        sessions=sessions,
        vault=vault,
        collect=collect,
        curators=curators,
        distill=distill,
        distillation=distillation,
        import_records=import_records,
        search=search,
    )
