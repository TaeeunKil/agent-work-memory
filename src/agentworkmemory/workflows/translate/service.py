import tempfile
from pathlib import Path

from agentworkmemory.services.curators.models import (
    CuratorRunRequest,
    CuratorRunStatus,
)
from agentworkmemory.services.curators.service import CuratorsService
from agentworkmemory.services.frontmatter import split_frontmatter
from agentworkmemory.services.translations import (
    Locale,
    TranslationService,
    TranslationStatus,
)
from agentworkmemory.services.vault.service import (
    VaultService,
    ensure_inside,
    remove_curator_workspace,
)
from agentworkmemory.services.vault.snapshot import VaultSnapshot
from agentworkmemory.services.wiki.service import WikiCatalogService
from agentworkmemory.workflows.translate.models import TranslateWikiPages
from agentworkmemory.workflows.translate.prompt import translation_prompt


class TranslateWikiWorkflow:
    def __init__(
        self,
        curators: CuratorsService,
        vault: VaultService,
        wiki: WikiCatalogService,
        translations: TranslationService,
    ):
        self.curators = curators
        self.vault = vault
        self.wiki = wiki
        self.translations = translations

    def pending_paths(self, locale: Locale, limit: int) -> tuple[Path, ...]:
        if limit < 1 or limit > 20:
            raise ValueError("translation limit must be between 1 and 20")
        pending: list[Path] = []
        for page in self.wiki.pages():
            if page.original_locale is locale:
                continue
            representation = self.translations.resolve(page.path, locale)
            if representation.status is TranslationStatus.CURRENT:
                continue
            pending.append(page.path)
            if len(pending) == limit:
                break
        return tuple(pending)

    def run(self, request: TranslateWikiPages) -> tuple[Path, ...]:
        self.curators.ensure_ready(request.runtime)
        changed: list[Path] = []
        for path in request.paths:
            representation = self.translations.resolve(path, request.locale)
            if representation.original_locale is request.locale:
                continue
            if representation.status is TranslationStatus.CURRENT:
                continue
            translated_body = self.translate_one(request, path)
            changed.append(
                self.translations.write(
                    path,
                    request.locale,
                    translated_body,
                    translator=request.runtime,
                )
            )
        return tuple(changed)

    def translate_one(self, request: TranslateWikiPages, path: Path) -> str:
        root = self.vault.require_path().resolve()
        source = (root / path).resolve()
        ensure_inside(root, source)
        if source.is_symlink() or not source.is_file():
            raise KeyError(f"unknown Wiki page: {path}")
        workspace_root = self.vault.config.state_dir / "translation-workspaces"
        workspace_root.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix="translate-", dir=workspace_root))
        try:
            workspace = temporary / "vault"
            target = workspace / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            snapshot = VaultSnapshot.capture(workspace)
            original = self.translations.resolve(path)
            result = self.curators.run(
                CuratorRunRequest(
                    runtime=request.runtime,
                    model=request.model,
                    vault_path=workspace,
                    prompt=translation_prompt(
                        path,
                        original.original_locale,
                        request.locale,
                    ),
                    content_access=request.content_access,
                )
            )
            if result.status is not CuratorRunStatus.SUCCEEDED:
                raise RuntimeError(
                    f"translator {request.runtime} ended with {result.status.value}"
                )
            self.vault.normalize_curator_workspace_permissions(workspace)
            changed = snapshot.changed_files()
            if changed != (path,):
                raise ValueError("translator must replace exactly the selected page")
            _, body = split_frontmatter(target.read_text(encoding="utf-8"))
            if not any(
                line.startswith("# ") and line[2:].strip()
                for line in body.splitlines()
            ):
                raise ValueError("translated Markdown needs an H1 heading")
            return body
        finally:
            remove_curator_workspace(temporary)
