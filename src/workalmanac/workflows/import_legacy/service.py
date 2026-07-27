import re
from hashlib import sha256
from pathlib import Path

from workalmanac.services.search.service import SearchService
from workalmanac.services.vault.service import VaultService, ensure_inside
from workalmanac.services.wiki.service import WikiCatalogService
from workalmanac.workflows.import_legacy.models import (
    ImportLegacyAlmanac,
    LegacyImportReceipt,
)

MAX_LEGACY_IMPORT_BYTES = 50 * 1024 * 1024


class ImportLegacyAlmanacWorkflow:
    def __init__(
        self,
        vault: VaultService,
        wiki: WikiCatalogService,
        search: SearchService,
    ):
        self.vault = vault
        self.wiki = wiki
        self.search = search

    def run(self, request: ImportLegacyAlmanac) -> LegacyImportReceipt:
        source_root, repository_root = legacy_pages_root(request.source)
        namespace = legacy_namespace(repository_root)
        vault_root = self.vault.require_path()
        target_root = (
            vault_root / "imports" / "repository-almanacs" / namespace
        ).resolve()
        ensure_inside(vault_root, target_root)
        target_root.mkdir(parents=True, exist_ok=True)
        discovered = 0
        copied = 0
        unchanged = 0
        total_bytes = 0
        for source in sorted(source_root.rglob("*.md")):
            if source.is_symlink():
                raise ValueError("legacy Almanac symlinks are not importable")
            if not source.is_file():
                continue
            discovered += 1
            content = source.read_bytes()
            total_bytes += len(content)
            if total_bytes > MAX_LEGACY_IMPORT_BYTES:
                raise ValueError("legacy Almanac import exceeds the 50 MB limit")
            content.decode("utf-8")
            relative = source.relative_to(source_root)
            target = (target_root / relative).resolve()
            ensure_inside(target_root, target)
            if target.is_file() and target.read_bytes() == content:
                unchanged += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            copied += 1
        self.wiki.refresh()
        self.search.refresh()
        return LegacyImportReceipt(
            namespace=namespace,
            files_discovered=discovered,
            files_copied=copied,
            files_unchanged=unchanged,
            target=target_root.relative_to(vault_root),
        )


def legacy_pages_root(value: Path) -> tuple[Path, Path]:
    source = value.expanduser().resolve()
    candidates = (
        (source / ".almanac" / "pages", source),
        (source / "pages", source.parent if source.name == ".almanac" else source),
        (
            source,
            source.parent.parent
            if source.name == "pages" and source.parent.name == ".almanac"
            else source.parent,
        ),
    )
    for pages, repository in candidates:
        if pages.is_dir() and any(pages.rglob("*.md")):
            return pages, repository
    raise ValueError("no legacy .almanac/pages Markdown tree found")


def legacy_namespace(repository_root: Path) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", repository_root.name.casefold()).strip("-")
    if not slug:
        slug = "repository"
    identity = sha256(str(repository_root).encode()).hexdigest()[:8]
    return f"{slug[:48]}-{identity}"
