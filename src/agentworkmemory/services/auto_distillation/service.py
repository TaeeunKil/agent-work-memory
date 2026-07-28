from datetime import UTC, datetime
from pathlib import Path

from agentworkmemory.services.auto_distillation.models import (
    AutoDistillSettings,
    AutoDistillStatus,
)
from agentworkmemory.services.auto_distillation.ports import (
    AutoDistillSchedulerAdapter,
)
from agentworkmemory.services.auto_distillation.store import AutoDistillStore


class AutoDistillationService:
    def __init__(
        self,
        adapter: AutoDistillSchedulerAdapter,
        store: AutoDistillStore,
        state_dir: Path,
    ):
        self.adapter = adapter
        self.store = store
        self.state_dir = state_dir

    def install(self, settings: AutoDistillSettings) -> AutoDistillStatus:
        if not self.adapter.available():
            raise RuntimeError(
                "automatic distillation is unavailable on this platform"
            )
        now = datetime.now(UTC)
        if settings.expires_at <= now:
            raise ValueError("automatic distill standing grant is already expired")
        installed = settings.model_copy(update={"installed_at": now})
        self.adapter.install(installed, self.state_dir)
        self.store.save(installed)
        return self.status()

    def settings(self) -> AutoDistillSettings:
        settings = self.store.load()
        if settings is None:
            raise RuntimeError("automatic distillation is not configured")
        return settings

    def available_batch_limit(self, now: datetime | None = None) -> int:
        settings = self.settings()
        current = now or datetime.now(UTC)
        if current >= settings.expires_at:
            return 0
        remaining = settings.max_sessions_total - settings.sessions_reserved
        return min(settings.limit, max(0, remaining))

    def reserve_sessions(self, count: int) -> AutoDistillSettings:
        if count < 1:
            raise ValueError("reserved session count must be positive")
        settings = self.settings()
        reserved = settings.sessions_reserved + count
        if reserved > settings.max_sessions_total:
            raise ValueError("automatic distill standing grant is exhausted")
        updated = settings.model_copy(
            update={"sessions_reserved": reserved}
        )
        self.store.save(updated)
        return updated

    def refund_sessions(self, count: int) -> AutoDistillSettings:
        if count < 1:
            raise ValueError("refunded session count must be positive")
        settings = self.settings()
        if count > settings.sessions_reserved:
            raise ValueError("cannot refund more sessions than were reserved")
        updated = settings.model_copy(
            update={"sessions_reserved": settings.sessions_reserved - count}
        )
        self.store.save(updated)
        return updated

    def status(self) -> AutoDistillStatus:
        available = self.adapter.available()
        installed = available and self.adapter.installed()
        if not available:
            message = "Automatic distillation is unavailable on this platform."
        elif installed:
            message = (
                f"Automatic distillation is installed as {self.adapter.task_name}."
            )
        else:
            message = "Automatic distillation is not installed."
        return AutoDistillStatus(
            available=available,
            installed=installed,
            task_name=self.adapter.task_name,
            message=message,
            settings=self.store.load(),
            next_run_at=self.adapter.next_run_at() if installed else None,
        )

    def remove(self) -> None:
        if self.adapter.available() and self.adapter.installed():
            self.adapter.remove()
        self.store.remove()
