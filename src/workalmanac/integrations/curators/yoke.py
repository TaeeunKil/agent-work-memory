import os
import shutil
import sys
from pathlib import Path

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
from yoke.providers.codex import Codex

from workalmanac.agents import distill_instructions
from workalmanac.integrations.curators.yoke_utf8 import enable_yoke_codex_utf8
from workalmanac.services.curators.models import (
    ContentAccess,
    CuratorReadiness,
    CuratorRunRequest,
    CuratorRunResult,
    CuratorRunStatus,
)

CLAUDE_WIKI_TOOLS = ("Read", "Write", "Edit", "Glob", "Grep", "LS")
CURATOR_TIMEOUT_SECONDS = 30 * 60


class YokeCuratorAdapter:
    def __init__(self, runtime: str, runtime_root: Path):
        if runtime not in {"codex", "claude"}:
            raise ValueError(f"unsupported Yoke curator runtime: {runtime}")
        self.runtime = runtime
        self.runtime_root = runtime_root

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
        try:
            run = self.harness(request.vault_path).run_sync(
                request.prompt,
                run_options(request),
            )
        except (OSError, TimeoutError, ValidationError, YokeError) as error:
            return CuratorRunResult(
                runtime=self.runtime,
                status=CuratorRunStatus.FAILED,
                output_text=(f"{self.runtime} curator failed ({type(error).__name__})"),
            )
        output = run.output or (
            run.failure.message if run.failure is not None else str(run.status)
        )
        return CuratorRunResult(
            runtime=self.runtime,
            status=CuratorRunStatus(str(run.status)),
            output_text=output,
            provider_session_id=run.provider_session_id,
        )

    def harness(self, cwd: Path) -> Harness:
        surface = curator_surface(self.runtime, sys.platform)
        if surface == "codex_app_server":
            enable_yoke_codex_utf8()
        harness = Harness(
            provider=self.runtime,
            surface=surface,
            agent=Agent(
                instructions=distill_instructions(),
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
                Codex(
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


def run_options(request: CuratorRunRequest) -> RunOptions:
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
    )
    return RunOptions(
        model=request.model,
        timeout_seconds=CURATOR_TIMEOUT_SECONDS,
        permissions=permissions,
        provider=provider,
    )
