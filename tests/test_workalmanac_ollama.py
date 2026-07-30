import json
from pathlib import Path

import httpx
import pytest

from workalmanac.app import create_app
from workalmanac.cli import build_parser, distill_content_access
from workalmanac.integrations.curators.ollama import (
    LocalWikiChangeSet,
    LocalWikiFile,
    OllamaCuratorAdapter,
)
from workalmanac.services.curators.models import (
    ContentAccess,
    CuratorRunRequest,
    CuratorRunStatus,
)
from workalmanac.services.distillation.models import DistillStatus
from workalmanac.settings import WorkAlmanacConfig
from workalmanac.workflows.distill import DistillSessions


def test_ollama_readiness_lists_local_models():
    adapter = OllamaCuratorAdapter(transport=model_transport(("qwen3:8b", "gemma3")))

    readiness = adapter.check()

    assert readiness.available
    assert readiness.message == "Ollama ready: gemma3, qwen3:8b"


def test_local_distill_uses_structured_output_and_existing_wiki(tmp_path: Path):
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return tags_response(("qwen3:8b",))
        payload = json.loads(request.content)
        requests.append(payload)
        change_set = LocalWikiChangeSet(
            summary="recorded local decision",
            files=(
                LocalWikiFile(
                    path="decisions/local-curator.md",
                    content=(
                        "---\n"
                        "tags:\n"
                        "  - local-llm\n"
                        "---\n"
                        "# Local curator\n\n"
                        "Use a structured local curator.\n"
                    ),
                ),
            ),
        )
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": change_set.model_dump_json(),
                },
                "done": True,
            },
        )

    adapter = OllamaCuratorAdapter(transport=httpx.MockTransport(handler))
    app = create_app(
        WorkAlmanacConfig(state_dir=tmp_path / "state", vault_path=None),
        curator_adapters=(adapter,),
    )
    vault = app.vault.initialize(tmp_path / "vault")
    (vault / "systems" / "existing.md").write_text(
        "# Existing system\n\nKeep this context visible.\n",
        encoding="utf-8",
    )
    session = app.sessions.add_manual_note(
        "Record the local curator decision.",
        title="Local curator decision",
    )
    app.vault.refresh_session(session, app.sessions.events(session.session_id))

    receipt = app.distill.run(
        DistillSessions(
            session_ids=(session.session_id,),
            runtime="ollama",
            model="qwen3:8b",
            content_access=ContentAccess.SELECTED_LOCAL,
        )
    )

    assert receipt.status is DistillStatus.SUCCEEDED
    assert receipt.changed_files == (Path("decisions/local-curator.md"),)
    assert (vault / receipt.changed_files[0]).is_file()
    payload = requests[0]
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"] == {"temperature": 0}
    assert isinstance(payload["format"], dict)
    messages = payload["messages"]
    assert "Record the local curator decision." in messages[1]["content"]
    assert "Keep this context visible." in messages[1]["content"]
    assert (vault / "decisions" / "_index.md").is_file()


def test_ollama_rejects_remote_content_without_network(tmp_path: Path):
    adapter = OllamaCuratorAdapter(
        transport=httpx.MockTransport(
            lambda request: pytest.fail("network should not be called")
        )
    )

    with pytest.raises(ValueError, match="selected-remote"):
        adapter.run(
            CuratorRunRequest(
                runtime="ollama",
                model="qwen3:8b",
                vault_path=tmp_path,
                prompt="distill",
                content_access=ContentAccess.SELECTED_REMOTE,
            )
        )


def test_ollama_path_escape_fails_inside_disposable_workspace(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        change_set = LocalWikiChangeSet(
            files=(
                LocalWikiFile(
                    path="decisions/../../outside.md",
                    content="# Escaped\n",
                ),
            )
        )
        return httpx.Response(
            200,
            json={"message": {"content": change_set.model_dump_json()}},
        )

    adapter = OllamaCuratorAdapter(transport=httpx.MockTransport(handler))

    result = adapter.run(
        CuratorRunRequest(
            runtime="ollama",
            model="qwen3:8b",
            vault_path=tmp_path / "vault",
            prompt="distill",
            content_access=ContentAccess.SELECTED_LOCAL,
        )
    )

    assert result.status is CuratorRunStatus.FAILED
    assert not (tmp_path / "outside.md").exists()


def test_ollama_requires_explicit_model_when_multiple_are_installed(
    tmp_path: Path,
):
    adapter = OllamaCuratorAdapter(transport=model_transport(("qwen3:8b", "gemma3")))

    result = adapter.run(
        CuratorRunRequest(
            runtime="ollama",
            vault_path=tmp_path,
            prompt="distill",
            content_access=ContentAccess.METADATA_ONLY,
        )
    )

    assert result.status is CuratorRunStatus.FAILED
    assert result.output_text == "local curator failed (ValueError)"


def test_ollama_endpoint_must_remain_on_loopback():
    with pytest.raises(ValueError, match="loopback"):
        OllamaCuratorAdapter("https://example.com")


def test_cli_exposes_explicit_local_content_policy():
    args = build_parser().parse_args(
        (
            "distill",
            "ses_example",
            "--using",
            "ollama",
            "--model",
            "qwen3:8b",
            "--allow-local-content",
        )
    )

    assert distill_content_access(args) is ContentAccess.SELECTED_LOCAL


def model_transport(models: tuple[str, ...]) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: tags_response(models))


def tags_response(models: tuple[str, ...]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"models": [{"name": model} for model in models]},
    )
