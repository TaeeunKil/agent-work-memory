import re
import shutil
import subprocess
from pathlib import Path

from agentworkmemory.integrations.processes import hidden_process_creation_flags
from agentworkmemory.services.vault_repository.models import VaultRepositoryStatus

COMMAND_TIMEOUT_SECONDS = 900
URL_CREDENTIALS = re.compile(r"(?i)(https?://)([^/\s@]+)@")


class GitVaultRepositoryAdapter:
    def __init__(self, executable: str | None = None):
        self.executable = executable or shutil.which("git")

    def clone(self, repository: str, destination: Path) -> None:
        if destination.exists() and any(destination.iterdir()):
            raise ValueError(f"Vault destination is not empty: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.run(("clone", repository, str(destination)))

    def initialize(self, root: Path, repository: str) -> None:
        if not (root / ".git").exists():
            self.run(("init", "-b", "main"), cwd=root)
        remotes = self.run(("remote",), cwd=root).splitlines()
        if "origin" not in remotes:
            self.run(("remote", "add", "origin", repository), cwd=root)
            return
        current = self.run(("remote", "get-url", "origin"), cwd=root).strip()
        if current != repository:
            raise ValueError(
                "Vault Git remote `origin` does not match the repository "
                "requested for publishing"
            )

    def status(self, root: Path) -> VaultRepositoryStatus:
        self.require_repository(root)
        porcelain = self.run(("status", "--porcelain=v1", "--branch"), cwd=root)
        lines = porcelain.splitlines()
        branch = parse_branch(lines[0] if lines else "")
        remote = self.run(("remote", "get-url", "origin"), cwd=root).strip()
        changes = len(lines[1:])
        return VaultRepositoryStatus(
            path=root,
            branch=branch,
            remote=redact_git_output(remote),
            clean=changes == 0,
            changes=changes,
        )

    def commit_all(self, root: Path, message: str) -> bool:
        self.require_repository(root)
        self.run(("add", "-A"), cwd=root)
        if not self.run(("status", "--porcelain"), cwd=root).strip():
            return False
        self.run(("commit", "-m", message), cwd=root)
        return True

    def pull_rebase(self, root: Path) -> None:
        status = self.status(root)
        self.run(("pull", "--rebase", "origin", status.branch), cwd=root)

    def push(self, root: Path) -> None:
        status = self.status(root)
        self.run(("push", "-u", "origin", status.branch), cwd=root)

    def require_repository(self, root: Path) -> None:
        if not (root / ".git").exists():
            raise RuntimeError(
                "Configured Vault is not a Git repository; "
                "run `awm vault publish <repository>` first"
            )

    def run(self, arguments: tuple[str, ...], *, cwd: Path | None = None) -> str:
        if self.executable is None:
            raise RuntimeError("Git executable was not found")
        try:
            completed = subprocess.run(
                (self.executable, *arguments),
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=True,
                timeout=COMMAND_TIMEOUT_SECONDS,
                creationflags=hidden_process_creation_flags(),
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("Git operation timed out") from error
        except OSError as error:
            raise RuntimeError("Git operation could not start") from error
        except subprocess.CalledProcessError as error:
            detail = decode_process_output(error.stderr or error.stdout)
            raise RuntimeError(
                f"Git operation failed: {redact_git_output(detail)}"
            ) from error
        return decode_process_output(completed.stdout)


def parse_branch(header: str) -> str:
    if not header.startswith("## "):
        raise RuntimeError("Git status did not report the current branch")
    branch = header[3:].split("...", 1)[0].strip()
    if not branch or branch == "HEAD (no branch)":
        raise RuntimeError("Vault repository is not on a named branch")
    return branch


def decode_process_output(content: bytes) -> str:
    return content.decode("utf-8", errors="replace").strip()


def redact_git_output(content: str) -> str:
    return URL_CREDENTIALS.sub(r"\1***@", content)
