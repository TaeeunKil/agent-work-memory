import os

from workalmanac.integrations.automation.unsupported import (
    UnsupportedSchedulerAdapter,
)
from workalmanac.integrations.automation.windows import WindowsSchedulerAdapter
from workalmanac.services.automation.ports import SchedulerAdapter


def default_scheduler_adapter() -> SchedulerAdapter:
    if os.name == "nt":
        return WindowsSchedulerAdapter()
    return UnsupportedSchedulerAdapter()


__all__ = ["default_scheduler_adapter"]
