from datetime import datetime
from typing import Protocol


class ActivityProcessProbe(Protocol):
    def running(self, process_id: int, activity_started_at: datetime) -> bool: ...
