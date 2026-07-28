import os

from workalmanac.integrations.auto_distillation.unsupported import (
    UnsupportedAutoDistillSchedulerAdapter,
)
from workalmanac.integrations.auto_distillation.windows import (
    WindowsAutoDistillSchedulerAdapter,
)
from workalmanac.services.auto_distillation.ports import (
    AutoDistillSchedulerAdapter,
)


def default_auto_distill_scheduler_adapter() -> AutoDistillSchedulerAdapter:
    if os.name == "nt":
        return WindowsAutoDistillSchedulerAdapter()
    return UnsupportedAutoDistillSchedulerAdapter()


__all__ = ["default_auto_distill_scheduler_adapter"]
