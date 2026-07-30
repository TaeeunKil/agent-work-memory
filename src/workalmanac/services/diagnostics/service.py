from pathlib import Path

from workalmanac.services.automation.service import AutomationService
from workalmanac.services.curators.service import CuratorsService
from workalmanac.services.diagnostics.models import (
    DiagnosticCheck,
    DiagnosticStatus,
)
from workalmanac.services.vault.service import VaultService
from workalmanac.settings import WorkAlmanacConfig


class DiagnosticsService:
    def __init__(
        self,
        config: WorkAlmanacConfig,
        vault: VaultService,
        automation: AutomationService,
        curators: CuratorsService,
    ):
        self.config = config
        self.vault = vault
        self.automation = automation
        self.curators = curators

    def run(
        self,
        home: Path,
        *,
        include_runtimes: bool = False,
    ) -> tuple[DiagnosticCheck, ...]:
        checks = [
            vault_check(self.vault),
            database_check(self.config),
            transcript_check(home / ".codex" / "sessions", "codex"),
            transcript_check(home / ".claude" / "projects", "claude"),
            automation_check(self.automation),
        ]
        if include_runtimes:
            checks.extend(
                DiagnosticCheck(
                    name=f"runtime:{readiness.runtime}",
                    status=(
                        DiagnosticStatus.OK
                        if readiness.available
                        else DiagnosticStatus.WARNING
                    ),
                    message=readiness.message,
                )
                for readiness in self.curators.readiness()
            )
        return tuple(checks)


def vault_check(vault: VaultService) -> DiagnosticCheck:
    try:
        path = vault.require_path()
    except RuntimeError:
        return DiagnosticCheck(
            name="vault",
            status=DiagnosticStatus.ERROR,
            message="Not configured; run `wa setup <vault>`.",
        )
    if not path.is_dir():
        return DiagnosticCheck(
            name="vault",
            status=DiagnosticStatus.ERROR,
            message="Configured Vault directory is missing.",
        )
    return DiagnosticCheck(
        name="vault",
        status=DiagnosticStatus.OK,
        message="Private Markdown Vault is configured.",
    )


def database_check(config: WorkAlmanacConfig) -> DiagnosticCheck:
    return DiagnosticCheck(
        name="database",
        status=(
            DiagnosticStatus.OK
            if config.database_path.is_file()
            else DiagnosticStatus.WARNING
        ),
        message=(
            "Private local database is ready."
            if config.database_path.is_file()
            else "Database will be created on first use."
        ),
    )


def transcript_check(path: Path, provider: str) -> DiagnosticCheck:
    available = path.is_dir() and next(path.rglob("*.jsonl"), None) is not None
    return DiagnosticCheck(
        name=f"transcripts:{provider}",
        status=DiagnosticStatus.OK if available else DiagnosticStatus.WARNING,
        message=(
            f"{provider.title()} transcript store found."
            if available
            else f"No {provider.title()} transcript store found yet."
        ),
    )


def automation_check(automation: AutomationService) -> DiagnosticCheck:
    status = automation.status()
    if status.installed:
        level = DiagnosticStatus.OK
    elif status.available:
        level = DiagnosticStatus.WARNING
    else:
        level = DiagnosticStatus.WARNING
    return DiagnosticCheck(
        name="automation",
        status=level,
        message=status.message,
    )
