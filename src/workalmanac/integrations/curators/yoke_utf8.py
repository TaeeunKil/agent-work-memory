import os
import subprocess
from pathlib import Path

from yoke.providers.codex_app.process import JsonRpcLineProcess


def enable_yoke_codex_utf8() -> None:
    """Keep Yoke 0.1.x from decoding Codex JSON-RPC with a Windows locale."""
    JsonRpcLineProcess.start = classmethod(start_codex_process_utf8)


def start_codex_process_utf8(
    cls: type[JsonRpcLineProcess],
    command: str,
    args: tuple[str, ...],
    cwd: Path,
    env: dict[str, str] | None,
) -> JsonRpcLineProcess:
    process_env = dict(os.environ)
    process_env.setdefault("YOKE_INTERNAL_SESSION", "1")
    if env is not None:
        process_env.update(env)
    child = subprocess.Popen(
        (command, *args),
        cwd=cwd,
        env=process_env,
        text=True,
        encoding="utf-8",
        errors="strict",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        start_new_session=True,
    )
    return cls(child)
