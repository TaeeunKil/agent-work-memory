import json
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import httpx
from pydantic import Field, StringConstraints, ValidationError

from workalmanac.agents import distill_instructions
from workalmanac.core import WorkAlmanacModel
from workalmanac.services.curators.models import (
    ContentAccess,
    CuratorReadiness,
    CuratorRunRequest,
    CuratorRunResult,
    CuratorRunStatus,
)
from workalmanac.services.vault.service import (
    allowed_distill_path,
    ensure_inside,
)

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
MAX_EXISTING_WIKI_CHARS = 80_000
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_CHANGED_FILES = 64
MAX_CHANGED_FILE_CHARS = 1_000_000


class LocalWikiFile(WorkAlmanacModel):
    path: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    content: Annotated[str, StringConstraints(max_length=MAX_CHANGED_FILE_CHARS)]


class LocalWikiChangeSet(WorkAlmanacModel):
    summary: Annotated[str, StringConstraints(max_length=2_000)] = ""
    files: tuple[LocalWikiFile, ...] = Field(
        default=(),
        max_length=MAX_CHANGED_FILES,
    )


class OllamaCuratorAdapter:
    runtime = "ollama"

    def __init__(
        self,
        endpoint: str = DEFAULT_OLLAMA_URL,
        *,
        transport: httpx.BaseTransport | None = None,
    ):
        self.endpoint = validate_local_endpoint(endpoint)
        self.transport = transport

    def check(self) -> CuratorReadiness:
        try:
            models = self.model_names()
        except (httpx.HTTPError, ValueError) as error:
            return CuratorReadiness(
                runtime=self.runtime,
                available=False,
                message=f"Ollama is not ready ({type(error).__name__}).",
                repair="Start Ollama and run `ollama pull <model>`.",
            )
        if not models:
            return CuratorReadiness(
                runtime=self.runtime,
                available=False,
                message="Ollama is running but has no local models.",
                repair="Run `ollama pull <model>`.",
            )
        return CuratorReadiness(
            runtime=self.runtime,
            available=True,
            message=f"Ollama ready: {', '.join(models)}",
        )

    def run(self, request: CuratorRunRequest) -> CuratorRunResult:
        if request.runtime != self.runtime:
            raise ValueError(
                f"curator request runtime {request.runtime!r} does not match "
                f"adapter {self.runtime!r}"
            )
        if request.content_access is ContentAccess.SELECTED_REMOTE:
            raise ValueError("ollama is local; selected-remote is not allowed")
        try:
            model = request.model or self.only_model()
            response = self.chat(
                model,
                local_curator_prompt(request),
                request.vault_path,
            )
            apply_local_changes(request.vault_path, response)
        except (
            httpx.HTTPError,
            KeyError,
            OSError,
            UnicodeError,
            ValidationError,
            ValueError,
        ) as error:
            return CuratorRunResult(
                runtime=self.runtime,
                status=CuratorRunStatus.FAILED,
                output_text=f"local curator failed ({type(error).__name__})",
            )
        return CuratorRunResult(
            runtime=self.runtime,
            status=CuratorRunStatus.SUCCEEDED,
            output_text=response.summary or "local curator completed",
        )

    def model_names(self) -> tuple[str, ...]:
        with self.client() as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            payload = response.json()
        models = payload.get("models")
        if not isinstance(models, list):
            raise ValueError("Ollama model response is malformed")
        names = {
            model.get("name")
            for model in models
            if isinstance(model, dict) and isinstance(model.get("name"), str)
        }
        return tuple(sorted(names))

    def only_model(self) -> str:
        models = self.model_names()
        if len(models) != 1:
            raise ValueError("choose an Ollama model explicitly with --model")
        return models[0]

    def chat(
        self,
        model: str,
        prompt: str,
        vault_path: Path,
    ) -> LocalWikiChangeSet:
        context = existing_wiki_context(vault_path)
        schema = LocalWikiChangeSet.model_json_schema()
        payload = {
            "model": model,
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0},
            "messages": [
                {
                    "role": "system",
                    "content": local_system_prompt(schema),
                },
                {
                    "role": "user",
                    "content": f"{prompt}\n\nExisting durable Wiki:\n{context}",
                },
            ],
        }
        with self.client() as client:
            response = client.post("/api/chat", json=payload)
            response.raise_for_status()
            if len(response.content) > MAX_RESPONSE_BYTES:
                raise ValueError("Ollama curator response is too large")
            raw = response.json()
        message = raw.get("message")
        if not isinstance(message, dict) or not isinstance(
            message.get("content"),
            str,
        ):
            raise ValueError("Ollama chat response is malformed")
        return LocalWikiChangeSet.model_validate_json(message["content"])

    def client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.endpoint,
            timeout=httpx.Timeout(600.0, connect=2.0),
            transport=self.transport,
        )


def validate_local_endpoint(value: str) -> str:
    endpoint = value.strip().rstrip("/")
    parsed = urlparse(endpoint)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Ollama endpoint must be a loopback HTTP origin")
    return endpoint


def local_system_prompt(schema: dict[str, object]) -> str:
    return (
        f"{distill_instructions()}\n\n"
        "You have no filesystem tools. Return only JSON matching this schema. "
        "Each files item is a complete replacement or new Markdown page. "
        "Omit unchanged pages and never return deletions, indexes, or inbox files.\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )


def local_curator_prompt(request: CuratorRunRequest) -> str:
    return (
        f"{request.prompt}\n"
        "Return complete content for every durable Markdown page you change."
    )


def existing_wiki_context(vault_path: Path) -> str:
    chunks: list[str] = []
    remaining = MAX_EXISTING_WIKI_CHARS
    for path in sorted(vault_path.rglob("*.md")):
        relative = path.relative_to(vault_path)
        if not allowed_distill_path(relative) or path.is_symlink():
            continue
        raw = path.read_text(encoding="utf-8")
        header = f"\n--- FILE: {relative.as_posix()} ---\n"
        available = max(0, remaining - len(header))
        if available == 0:
            break
        content = raw[:available]
        chunks.extend((header, content))
        remaining -= len(header) + len(content)
        if len(content) < len(raw):
            chunks.append("\n[Existing Wiki context truncated.]\n")
            break
    return "".join(chunks) or "(No durable pages yet.)"


def apply_local_changes(vault_path: Path, changes: LocalWikiChangeSet) -> None:
    seen: set[Path] = set()
    total_chars = 0
    for change in changes.files:
        relative = Path(change.path.replace("\\", "/"))
        if relative in seen:
            raise ValueError(f"duplicate local curator path: {relative}")
        if not allowed_distill_path(relative):
            raise ValueError(f"local curator returned forbidden path: {relative}")
        target = (vault_path / relative).resolve()
        ensure_inside(vault_path, target)
        total_chars += len(change.content)
        if total_chars > MAX_RESPONSE_BYTES:
            raise ValueError("local curator file changes are too large")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(change.content, encoding="utf-8")
        seen.add(relative)
