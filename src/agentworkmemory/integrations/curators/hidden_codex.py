import asyncio
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from yoke.errors import YokeError
from yoke.models import Harness, Readiness
from yoke.providers.codex import Codex
from yoke.providers.codex_cli import CodexCli, config_overrides, write_schema
from yoke.readiness import CommandCheck

from agentworkmemory.integrations.processes import hidden_process_creation_flags

ORIGINATOR_ENV = "CODEX_INTERNAL_ORIGINATOR_OVERRIDE"
YOKE_ORIGINATOR = "yoke_python"


class HiddenCodex(Codex):
    """Yoke Codex adapter whose Windows child processes never own a console."""

    def __init__(
        self,
        executable: str = "codex",
        env: dict[str, str] | None = None,
        config: dict[str, Any] | None = None,
        skip_git_repo_check: bool = False,
        additional_directories: tuple[str | Path, ...] = (),
    ) -> None:
        super().__init__(
            executable=executable,
            env=env,
            config=config,
            skip_git_repo_check=skip_git_repo_check,
            additional_directories=additional_directories,
        )
        self.cli = HiddenCodexCli(
            executable=executable,
            env=env,
            config=config,
        )

    async def check(self, harness: Harness) -> Readiness:
        try:
            result = await hidden_run_command(
                self.cli.executable,
                "login",
                "status",
                env=self.cli.env,
            )
        except FileNotFoundError:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message="codex not found on PATH",
                fix="Install Codex or pass a Codex adapter with the executable path.",
            )
        except TimeoutError:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message="codex login status timed out",
            )
        if result.code != 0:
            return Readiness(
                provider=self.provider,
                surface=self.surface,
                available=False,
                message=result.message or f"codex login status exited {result.code}",
                raw=result.stderr or result.stdout,
            )
        return Readiness(
            provider=self.provider,
            surface=self.surface,
            available=True,
            message=result.message or "codex authenticated",
        )


class HiddenCodexCli(CodexCli):
    async def run(
        self,
        prompt: str,
        *,
        cwd: Path,
        thread_id: str | None = None,
        model: str | None = None,
        sandbox: str | None = None,
        approval: str | None = None,
        effort: str | None = None,
        network: bool | None = None,
        web_search: str | None = None,
        output_schema: dict[str, Any] | None = None,
        skip_git_repo_check: bool = False,
        additional_directories: tuple[Path, ...] = (),
    ) -> AsyncIterator[dict[str, Any]]:
        schema_path: Path | None = None
        try:
            args = [self.executable, "exec", "--json", "--cd", str(cwd)]
            if model:
                args.extend(["--model", model])
            if sandbox:
                args.extend(["--sandbox", sandbox])
            if skip_git_repo_check:
                args.append("--skip-git-repo-check")
            for directory in additional_directories:
                args.extend(["--add-dir", str(directory)])
            for override in config_overrides(self.config):
                args.extend(["--config", override])
            if approval:
                args.extend(["--config", f"approval_policy={json.dumps(approval)}"])
            if effort:
                args.extend(
                    ["--config", f"model_reasoning_effort={json.dumps(effort)}"]
                )
            if network is not None:
                args.extend(
                    [
                        "--config",
                        "sandbox_workspace_write.network_access="
                        f"{str(network).lower()}",
                    ]
                )
            if web_search:
                args.extend(["--config", f"web_search={json.dumps(web_search)}"])
            if output_schema is not None:
                schema_path = write_schema(output_schema)
                args.extend(["--output-schema", str(schema_path)])
            if thread_id:
                args.extend(["resume", thread_id])
            args.append("-")

            process_env = dict(os.environ)
            if self.env is not None:
                process_env.update(self.env)
            process_env.setdefault(ORIGINATOR_ENV, YOKE_ORIGINATOR)
            process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env,
                creationflags=hidden_process_creation_flags(),
            )
            assert process.stdin is not None
            assert process.stdout is not None
            assert process.stderr is not None
            process.stdin.write(prompt.encode())
            await process.stdin.drain()
            process.stdin.close()

            async for raw in process.stdout:
                line = raw.decode().strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise YokeError(
                        f"Codex emitted invalid JSONL: {line}"
                    ) from error

            code = await process.wait()
            if code != 0:
                stderr = (await process.stderr.read()).decode().strip()
                raise YokeError(f"codex exec exited with code {code}: {stderr}")
        finally:
            if schema_path is not None:
                schema_path.unlink(missing_ok=True)


async def hidden_run_command(
    *args: str,
    env: dict[str, str] | None = None,
    timeout_seconds: float = 10,
) -> CommandCheck:
    process_env = dict(os.environ)
    if env is not None:
        process_env.update(env)
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=process_env,
        creationflags=hidden_process_creation_flags(),
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    return CommandCheck(
        code=process.returncode or 0,
        stdout=stdout.decode(errors="replace").strip(),
        stderr=stderr.decode(errors="replace").strip(),
    )
