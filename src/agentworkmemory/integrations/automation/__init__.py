import os
import sys

from agentworkmemory.integrations.automation.systemd import SystemdSchedulerAdapter
from agentworkmemory.integrations.automation.unsupported import (
    UnsupportedSchedulerAdapter,
)
from agentworkmemory.integrations.automation.windows import WindowsSchedulerAdapter
from agentworkmemory.services.automation.ports import SchedulerAdapter


def default_scheduler_adapter() -> SchedulerAdapter:
    if os.name == "nt":
        return WindowsSchedulerAdapter()
    if sys.platform.startswith("linux"):
        return SystemdSchedulerAdapter()
    return UnsupportedSchedulerAdapter()


__all__ = ["default_scheduler_adapter"]
