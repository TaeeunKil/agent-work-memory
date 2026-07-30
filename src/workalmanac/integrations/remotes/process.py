import shutil
import subprocess
import threading
from pathlib import Path
from typing import Protocol

from workalmanac.services.remotes.errors import (
    RemoteAccessError,
    RemoteAccessErrorKind,
)

SSH_OPTIONS = (
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=10",
    "-o",
    "ServerAliveInterval=15",
    "-o",
    "ServerAliveCountMax=2",
    "-o",
    "StrictHostKeyChecking=yes",
)


class SshRunner(Protocol):
    def capture(
        self,
        target: str,
        remote_command: str,
        *,
        timeout_seconds: int,
    ) -> bytes: ...

    def download(
        self,
        target: str,
        remote_command: str,
        destination: Path,
        *,
        timeout_seconds: int,
        max_bytes: int,
    ) -> None: ...


class OpenSshRunner:
    def __init__(self, executable: str | None = None):
        self.executable = executable or shutil.which("ssh")

    def capture(
        self,
        target: str,
        remote_command: str,
        *,
        timeout_seconds: int,
    ) -> bytes:
        completed = self.run(
            target,
            remote_command,
            timeout_seconds=timeout_seconds,
            stdout=subprocess.PIPE,
        )
        return completed.stdout

    def download(
        self,
        target: str,
        remote_command: str,
        destination: Path,
        *,
        timeout_seconds: int,
        max_bytes: int,
    ) -> None:
        if self.executable is None:
            raise RemoteAccessError(
                RemoteAccessErrorKind.UNAVAILABLE,
                "OpenSSH client was not found",
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            process = subprocess.Popen(
                (
                    self.executable,
                    *SSH_OPTIONS,
                    target,
                    remote_command,
                ),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            raise RemoteAccessError(
                RemoteAccessErrorKind.UNAVAILABLE,
                "SSH connection could not start",
            ) from error
        timed_out = threading.Event()

        def stop_for_timeout() -> None:
            timed_out.set()
            process.kill()

        timer = threading.Timer(timeout_seconds, stop_for_timeout)
        timer.start()
        total = 0
        try:
            if process.stdout is None:
                raise RemoteAccessError(
                    RemoteAccessErrorKind.UNAVAILABLE,
                    "SSH download stream was unavailable",
                )
            with destination.open("wb") as stream, process.stdout:
                while chunk := process.stdout.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        process.kill()
                        raise RemoteAccessError(
                            RemoteAccessErrorKind.LIMIT,
                            "remote snapshot archive exceeds the download limit",
                        )
                    stream.write(chunk)
            return_code = process.wait()
        finally:
            timer.cancel()
            if process.poll() is None:
                process.kill()
                process.wait()
        if timed_out.is_set():
            raise RemoteAccessError(
                RemoteAccessErrorKind.UNAVAILABLE,
                "SSH operation timed out",
            )
        if return_code != 0:
            raise RemoteAccessError(
                RemoteAccessErrorKind.UNAVAILABLE,
                "SSH connection or remote command failed",
            )

    def run(
        self,
        target: str,
        remote_command: str,
        *,
        timeout_seconds: int,
        stdout: int | object,
    ) -> subprocess.CompletedProcess[bytes]:
        if self.executable is None:
            raise RemoteAccessError(
                RemoteAccessErrorKind.UNAVAILABLE,
                "OpenSSH client was not found",
            )
        try:
            return subprocess.run(
                (
                    self.executable,
                    *SSH_OPTIONS,
                    target,
                    remote_command,
                ),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=subprocess.PIPE,
                check=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise RemoteAccessError(
                RemoteAccessErrorKind.UNAVAILABLE,
                "SSH operation timed out",
            ) from error
        except (OSError, subprocess.CalledProcessError) as error:
            raise RemoteAccessError(
                RemoteAccessErrorKind.UNAVAILABLE,
                "SSH connection or remote command failed",
            ) from error
