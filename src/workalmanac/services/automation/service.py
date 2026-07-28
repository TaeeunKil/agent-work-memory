from datetime import UTC, datetime
from pathlib import Path

from workalmanac.services.automation.models import (
    AutoSyncSettings,
    SchedulerStatus,
)
from workalmanac.services.automation.ports import SchedulerAdapter
from workalmanac.services.automation.store import AutomationStore


class AutomationService:
    def __init__(
        self,
        adapter: SchedulerAdapter,
        store: AutomationStore,
        state_dir: Path,
    ):
        self.adapter = adapter
        self.store = store
        self.state_dir = state_dir

    def install(self, settings: AutoSyncSettings) -> SchedulerStatus:
        if not self.adapter.available():
            raise RuntimeError("automatic collection is unavailable on this platform")
        installed = settings.model_copy(update={"installed_at": datetime.now(UTC)})
        self.adapter.install(installed, self.state_dir)
        self.store.save(installed)
        return self.status()

    def status(self) -> SchedulerStatus:
        available = self.adapter.available()
        installed = available and self.adapter.installed()
        if not available:
            message = "Automatic collection is unavailable on this platform."
        elif installed:
            message = f"Automatic collection is installed as {self.adapter.task_name}."
        else:
            message = "Automatic collection is not installed."
        return SchedulerStatus(
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
