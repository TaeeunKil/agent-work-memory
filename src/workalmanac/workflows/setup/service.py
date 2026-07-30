from workalmanac.services.automation.models import AutoSyncSettings
from workalmanac.services.automation.service import AutomationService
from workalmanac.services.vault.service import VaultService
from workalmanac.services.wiki.service import WikiCatalogService
from workalmanac.workflows.setup.models import (
    SetupWorkAlmanac,
    SetupWorkAlmanacResult,
)
from workalmanac.workflows.sync.models import SyncAgentRecords
from workalmanac.workflows.sync.service import SyncAgentRecordsWorkflow


class SetupWorkAlmanacWorkflow:
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

    def run(self, request: SetupWorkAlmanac) -> SetupWorkAlmanacResult:
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
        return SetupWorkAlmanacResult(
            vault_path=vault_path,
            sync=sync_receipt,
            automation_installed=automation_installed,
        )
