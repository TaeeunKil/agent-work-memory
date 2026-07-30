from pathlib import Path

from workalmanac.services.auto_distillation.service import (
    AutoDistillationService,
)
from workalmanac.services.automation.service import AutomationService
from workalmanac.services.curators.service import CuratorsService
from workalmanac.services.diagnostics.models import (
    DiagnosticCheck,
    DiagnosticStatus,
)
from workalmanac.services.remotes.models import RemoteSyncState
from workalmanac.services.remotes.service import RemotesService
from workalmanac.services.sessions.service import SessionsService
from workalmanac.services.vault.service import VaultService
from workalmanac.services.wiki.service import WikiCatalogService
from workalmanac.settings import WorkAlmanacConfig


class DiagnosticsService:
    def __init__(
        self,
        config: WorkAlmanacConfig,
        vault: VaultService,
        automation: AutomationService,
        auto_distillation: AutoDistillationService,
        curators: CuratorsService,
        sessions: SessionsService,
        wiki: WikiCatalogService,
        remotes: RemotesService,
    ):
        self.config = config
        self.vault = vault
        self.automation = automation
        self.auto_distillation = auto_distillation
        self.curators = curators
        self.sessions = sessions
        self.wiki = wiki
        self.remotes = remotes

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
            auto_distillation_check(self.auto_distillation),
            knowledge_check(self.sessions, self.wiki),
            remotes_check(self.remotes),
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


def auto_distillation_check(
    automation: AutoDistillationService,
) -> DiagnosticCheck:
    status = automation.status()
    return DiagnosticCheck(
        name="auto-distill",
        status=(
            DiagnosticStatus.OK
            if status.installed
            else DiagnosticStatus.WARNING
        ),
        message=status.message,
    )


def knowledge_check(
    sessions: SessionsService,
    wiki: WikiCatalogService,
) -> DiagnosticCheck:
    retained = sessions.list()
    captured = tuple(session for session in retained if session.content_captured)
    pending = tuple(
        session
        for session in captured
        if session.distilled_at is None
    )
    try:
        durable = tuple(
            page for page in wiki.pages() if page.category != "imports"
        )
    except RuntimeError:
        durable = ()
    if durable:
        return DiagnosticCheck(
            name="knowledge",
            status=DiagnosticStatus.OK,
            message=(
                f"{len(durable)} durable Wiki page(s); "
                f"{len(pending)} captured session(s) await distillation."
            ),
        )
    if pending:
        return DiagnosticCheck(
            name="knowledge",
            status=DiagnosticStatus.WARNING,
            message=(
                f"{len(pending)} captured session(s), but no durable Wiki pages. "
                "Sync retains evidence only; use `wa distill <session-id> "
                "--using <runtime>` to promote selected work."
            ),
        )
    if retained:
        return DiagnosticCheck(
            name="knowledge",
            status=DiagnosticStatus.WARNING,
            message=(
                f"{len(retained)} session(s) retained as metadata only. "
                "Use `wa sync --include-content` before distillation."
            ),
        )
    return DiagnosticCheck(
        name="knowledge",
        status=DiagnosticStatus.WARNING,
        message="No sessions retained yet; run `wa sync --include-content`.",
    )


def remotes_check(remotes: RemotesService) -> DiagnosticCheck:
    overviews = remotes.list()
    if not overviews:
        return DiagnosticCheck(
            name="remotes",
            status=DiagnosticStatus.OK,
            message="No SSH remotes registered.",
        )
    failed = sum(
        overview.status.state is RemoteSyncState.FAILED
        for overview in overviews
    )
    waiting = sum(
        overview.status.state is RemoteSyncState.NEVER
        for overview in overviews
    )
    if failed:
        return DiagnosticCheck(
            name="remotes",
            status=DiagnosticStatus.WARNING,
            message=(
                f"{len(overviews)} registered; {failed} failed most recently. "
                "Run `wa remote list` for bounded status details."
            ),
        )
    if waiting:
        return DiagnosticCheck(
            name="remotes",
            status=DiagnosticStatus.WARNING,
            message=(
                f"{len(overviews)} registered; {waiting} not synced yet. "
                "Run `wa remote sync`."
            ),
        )
    return DiagnosticCheck(
        name="remotes",
        status=DiagnosticStatus.OK,
        message=f"{len(overviews)} SSH remote(s) synced successfully.",
    )
