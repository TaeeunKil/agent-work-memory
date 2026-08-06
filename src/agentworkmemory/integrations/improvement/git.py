import re
import shutil
import subprocess
from pathlib import Path

from agentworkmemory.integrations.processes import hidden_process_creation_flags

COMMAND_TIMEOUT_SECONDS = 10
MAX_OUTPUT_BYTES = 4096
URL_CREDENTIALS = re.compile(r"(?i)(https?://)([^/\s@]+)@")


class GitRevisionReader:
    """Read one repository HEAD revision without mutating the checkout."""

    def __init__(self, executable: str | None = None):
        self.executable = executable or shutil.which("git")

    def head(self, repository: Path) -> str:
        if not repository.is_absolute():
            raise ValueError("Git revision lookup requires an absolute repository")
        if self.executable is None:
            raise RuntimeError("Git executable was not found")
        try:
            completed = subprocess.run(
                (self.executable, "rev-parse", "HEAD"),
                cwd=repository,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=True,
                timeout=COMMAND_TIMEOUT_SECONDS,
                creationflags=hidden_process_creation_flags(),
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("Git revision lookup timed out") from error
        except OSError as error:
            raise RuntimeError("Git revision lookup could not start") from error
        except subprocess.CalledProcessError as error:
            detail = sanitized_process_output(error.stderr or error.stdout)
            suffix = f": {detail}" if detail else ""
            raise RuntimeError(f"Git revision lookup failed{suffix}") from error

        revision = sanitized_process_output(completed.stdout)
        if not revision or "\n" in revision or "\r" in revision:
            raise RuntimeError("Git revision lookup returned an invalid revision")
        return revision


def sanitized_process_output(content: bytes | str) -> str:
    if isinstance(content, bytes):
        decoded = content[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    else:
        decoded = content[:MAX_OUTPUT_BYTES]
    sanitized = URL_CREDENTIALS.sub(r"\1***@", decoded).strip()
    if len(sanitized) > MAX_OUTPUT_BYTES:
        return sanitized[:MAX_OUTPUT_BYTES]
    return sanitized
