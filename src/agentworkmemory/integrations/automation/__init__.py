import os

from agentworkmemory.integrations.automation.unsupported import (
    UnsupportedSchedulerAdapter,
)
from agentworkmemory.integrations.automation.windows import WindowsSchedulerAdapter
from agentworkmemory.services.automation.ports import SchedulerAdapter


def default_scheduler_adapter() -> SchedulerAdapter:
    if os.name == "nt":
        return WindowsSchedulerAdapter()
    return UnsupportedSchedulerAdapter()


__all__ = ["default_scheduler_adapter"]
