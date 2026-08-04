import sys
from datetime import UTC, datetime, timedelta

import psutil

WINDOWS_CREATE_NO_WINDOW = 0x08000000
PROCESS_START_TOLERANCE = timedelta(seconds=2)


def hidden_process_creation_flags(platform: str | None = None) -> int:
    resolved = platform or sys.platform
    return WINDOWS_CREATE_NO_WINDOW if resolved == "win32" else 0


class PsutilActivityProcessProbe:
    def running(self, process_id: int, activity_started_at: datetime) -> bool:
        try:
            process = psutil.Process(process_id)
            created_at = datetime.fromtimestamp(process.create_time(), UTC)
            return (
                process.is_running()
                and process.status() != psutil.STATUS_ZOMBIE
                and created_at <= activity_started_at + PROCESS_START_TOLERANCE
            )
        except psutil.NoSuchProcess:
            return False
        except (OSError, psutil.AccessDenied):
            return True
