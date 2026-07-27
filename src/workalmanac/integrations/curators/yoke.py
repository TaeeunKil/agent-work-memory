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

from workalmanac.agents import distill_instructions
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
        except (FileNotFoundError, TimeoutError, ValidationError, YokeError) as error:
            return CuratorReadiness(
                runtime=self.runtime,
                available=False,
                message=str(error),
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
        except (FileNotFoundError, TimeoutError, ValidationError, YokeError) as error:
            return CuratorRunResult(
                runtime=self.runtime,
                status=CuratorRunStatus.FAILED,
                output_text=str(error),
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
        return Harness(
            provider=self.runtime,
            surface="codex_app_server" if self.runtime == "codex" else None,
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
