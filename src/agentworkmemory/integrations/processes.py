import sys

WINDOWS_CREATE_NO_WINDOW = 0x08000000


def hidden_process_creation_flags(platform: str | None = None) -> int:
    resolved = platform or sys.platform
    return WINDOWS_CREATE_NO_WINDOW if resolved == "win32" else 0
