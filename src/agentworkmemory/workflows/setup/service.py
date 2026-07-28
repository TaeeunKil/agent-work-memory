from agentworkmemory.services.automation.models import AutoSyncSettings
from agentworkmemory.services.automation.service import AutomationService
from agentworkmemory.services.vault.service import VaultService
from agentworkmemory.services.wiki.service import WikiCatalogService
from agentworkmemory.workflows.setup.models import (
    SetupAgentWorkMemory,
    SetupAgentWorkMemoryResult,
)
from agentworkmemory.workflows.sync.models import SyncAgentRecords
from agentworkmemory.workflows.sync.service import SyncAgentRecordsWorkflow


class SetupAgentWorkMemoryWorkflow:
    def __init__(
        self,
        vault: VaultService,
        wiki: WikiCatalogService,
        sync: SyncAgentRecordsWorkflow,
        automation: AutomationService,
    ):
        self.vault = vault
        self.wiki = wiki
        self.sync = sync
        self.automation = automation

    def run(self, request: SetupAgentWorkMemory) -> SetupAgentWorkMemoryResult:
        vault_path = self.vault.initialize(request.vault_path)
        self.wiki.refresh()
        sync_receipt = self.sync.run(
            SyncAgentRecords(
                providers=request.providers,
                home=request.home.expanduser().resolve(),
                include_content=request.include_content,
            )
        )
        automation_installed = False
        if request.auto_interval_minutes is not None:
            status = self.automation.install(
                AutoSyncSettings(
                    interval_minutes=request.auto_interval_minutes,
                    providers=request.providers,
                    home=request.home.expanduser().resolve(),
                    include_content=request.include_content,
                )
            )
            automation_installed = status.installed
        return SetupAgentWorkMemoryResult(
            vault_path=vault_path,
            sync=sync_receipt,
            automation_installed=automation_installed,
        )
