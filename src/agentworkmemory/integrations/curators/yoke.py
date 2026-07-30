import json
import os
import shutil
import sys
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path, PureWindowsPath
from typing import Any

from pydantic import ValidationError
from yoke import (
    Access,
    Agent,
    Approval,
    ClaudeOptions,
    CodexApproval,
    CodexAppServerOptions,
    CodexOptions,
    CodexSandbox,
    Harness,
    Permissions,
    ProviderOptions,
    RunOptions,
    Tools,
    YokeError,
)

from agentworkmemory.agents import distill_instructions
from agentworkmemory.integrations.curators.hidden_codex import HiddenCodex
from agentworkmemory.integrations.curators.yoke_utf8 import enable_yoke_codex_utf8
from agentworkmemory.services.curators.models import (
    ContentAccess,
    CuratorReadiness,
    CuratorRunRequest,
    CuratorRunResult,
    CuratorRunStatus,
)

CLAUDE_WIKI_TOOLS = ("Read", "Write", "Edit", "Glob", "Grep", "LS")
CURATOR_TIMEOUT_SECONDS = 30 * 60
WINDOWS_CURATOR_OUTPUT = ".awm-curator-output.json"
WINDOWS_CODEX_WRITE_INSTRUCTIONS = """

## Windows file handoff

Do not create or edit Vault Markdown directly. On Windows, newly created files
can remain owned only by the Codex sandbox account. Instead, use `node_repl`
with Node's `fs/promises.writeFile` to replace the existing
`.awm-curator-output.json` file with this JSON shape:

{"files":[{"path":"projects/example.md","content":"# Complete Markdown\\n"}]}

Include the complete final UTF-8 content of every page to create or replace.
Use an empty `files` array for a no-op. Do not write any other file.
""".rstrip()


class YokeCuratorAdapter:
    def __init__(
        self,
        runtime: str,
        runtime_root: Path,
        workspace_permission_repair: Callable[[Path], None] | None = None,
    ):
        if runtime not in {"codex", "claude"}:
            raise ValueError(f"unsupported Yoke curator runtime: {runtime}")
        self.runtime = runtime
        self.runtime_root = runtime_root
        self.workspace_permission_repair = workspace_permission_repair

    def check(self) -> CuratorReadiness:
        readiness_root = self.runtime_root.parent / "readiness"
        readiness_root.mkdir(parents=True, exist_ok=True)
        try:
            readiness = self.harness(readiness_root).check_sync()
            return CuratorReadiness(
                runtime=self.runtime,
                available=readiness.available,
                message=readiness.message,
                repair=readiness.fix,
            )
        except (OSError, TimeoutError, ValidationError, YokeError) as error:
            return CuratorReadiness(
                runtime=self.runtime,
                available=False,
                message=(
                    f"{self.runtime.title()} runtime check failed "
                    f"({type(error).__name__})."
                ),
                repair=(
                    f"Verify that {self.runtime.title()} is installed, "
                    "signed in, and executable."
                ),
            )

    def run(self, request: CuratorRunRequest) -> CuratorRunResult:
        if request.runtime != self.runtime:
            raise ValueError(
                f"curator request runtime {request.runtime!r} does not match "
                f"adapter {self.runtime!r}"
            )
        if request.content_access is ContentAccess.SELECTED_LOCAL:
            raise ValueError(
                f"{self.runtime} is a remote runtime; selected-local is not allowed"
            )
        output_path = windows_curator_output_path(
            request.vault_path,
            runtime=self.runtime,
            platform=sys.platform,
        )
        try:
            if output_path is not None:
                output_path.write_text('{"files":[]}\n', encoding="utf-8")
            surface = curator_surface(self.runtime, sys.platform)
            try:
                run = self.harness(request.vault_path).run_sync(
                    request.prompt,
                    run_options(request, surface=surface),
                )
            finally:
                if (
                    output_path is not None
                    and self.workspace_permission_repair is not None
                ):
                    self.workspace_permission_repair(request.vault_path)
            status = CuratorRunStatus(str(run.status))
            if status is CuratorRunStatus.SUCCEEDED and output_path is not None:
                apply_windows_curator_output(
                    request.vault_path,
                    output_path.read_text(encoding="utf-8"),
                )
        except (
            OSError,
            TimeoutError,
            ValidationError,
            ValueError,
            YokeError,
        ) as error:
            return CuratorRunResult(
                runtime=self.runtime,
                status=CuratorRunStatus.FAILED,
                output_text=(f"{self.runtime} curator failed ({type(error).__name__})"),
            )
        finally:
            if output_path is not None:
                with suppress(OSError):
                    output_path.unlink(missing_ok=True)
        output = run.output or (
            run.failure.message if run.failure is not None else str(run.status)
        )
        return CuratorRunResult(
            runtime=self.runtime,
            status=status,
            output_text=output,
            provider_session_id=run.provider_session_id,
        )

    def harness(self, cwd: Path) -> Harness:
        surface = curator_surface(self.runtime, sys.platform)
        if surface == "codex_app_server":
            enable_yoke_codex_utf8()
        instructions = distill_instructions()
        if surface == "codex_cli" and sys.platform == "win32":
            instructions = (
                f"{instructions.rstrip()}\n\n"
                f"{WINDOWS_CODEX_WRITE_INSTRUCTIONS}\n"
            )
        harness = Harness(
            provider=self.runtime,
            surface=surface,
            agent=Agent(
                instructions=instructions,
                tools=Tools(
                    read=True,
                    write=True,
                    shell=False,
                    web=False,
                    agent=False,
                ),
                permissions=Permissions(
                    access=Access.WRITE,
                    approval=Approval.NEVER,
                    network=False,
                ),
            ),
            cwd=cwd,
            runtime_root=self.runtime_root,
        )
        if surface == "codex_cli":
            harness.with_adapter(
                HiddenCodex(
                    executable=standalone_codex_executable(),
                    skip_git_repo_check=True,
                )
            )
        return harness


def curator_surface(runtime: str, platform: str) -> str | None:
    if runtime != "codex":
        return None
    if platform == "win32":
        return "codex_cli"
    return "codex_app_server"


def windows_curator_output_path(
    vault_path: Path,
    *,
    runtime: str,
    platform: str,
) -> Path | None:
    if runtime != "codex" or platform != "win32":
        return None
    return vault_path / WINDOWS_CURATOR_OUTPUT


def apply_windows_curator_output(vault_path: Path, raw: str) -> tuple[Path, ...]:
    payload: Any = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
        raise ValueError("Windows curator output must contain a files list")
    root = vault_path.resolve()
    written: list[Path] = []
    seen: set[Path] = set()
    for proposal in payload["files"]:
        if not isinstance(proposal, dict):
            raise ValueError("Windows curator file proposal must be an object")
        relative_text = proposal.get("path")
        content = proposal.get("content")
        if not isinstance(relative_text, str) or not isinstance(content, str):
            raise ValueError("Windows curator file proposal needs path and content")
        relative = Path(relative_text)
        if PureWindowsPath(relative_text).is_absolute() or relative in seen:
            raise ValueError("Windows curator file path is invalid or duplicated")
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise ValueError("Windows curator file path escapes the Vault") from error
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        seen.add(relative)
        written.append(relative)
    return tuple(written)


def standalone_codex_executable() -> str:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        installed = (
            Path(local_app_data)
            / "Programs"
            / "OpenAI"
            / "Codex"
            / "bin"
            / "codex.exe"
        )
        if installed.is_file():
            return str(installed)
    return shutil.which("codex") or "codex"


def run_options(
    request: CuratorRunRequest,
    *,
    surface: str | None = "codex_app_server",
) -> RunOptions:
    permissions = Permissions(
        access=Access.WRITE,
        approval=Approval.NEVER,
        network=False,
    )
    provider = (
        ProviderOptions(
            claude=ClaudeOptions(
                tools=CLAUDE_WIKI_TOOLS,
                allowed_tools=CLAUDE_WIKI_TOOLS,
                permission_mode="dontAsk",
                setting_sources=(),
                raw={"mcp_servers": {}, "strict_mcp_config": True},
            )
        )
        if request.runtime == "claude"
        else ProviderOptions(
            codex=CodexOptions(
                sandbox=CodexSandbox.WORKSPACE_WRITE,
                approval=CodexApproval.NEVER,
                network=False,
                app_server=CodexAppServerOptions(ephemeral=True),
                runtime_workspace_roots=(str(request.vault_path),),
            )
        )
        if surface == "codex_app_server"
        else None
    )
    return RunOptions(
        model=request.model,
        timeout_seconds=CURATOR_TIMEOUT_SECONDS,
        permissions=permissions,
        provider=provider,
    )
