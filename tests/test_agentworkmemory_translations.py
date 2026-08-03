from pathlib import Path

from agentworkmemory.services.curators.models import (
    ContentAccess,
    CuratorReadiness,
    CuratorRunRequest,
    CuratorRunResult,
    CuratorRunStatus,
)
from agentworkmemory.services.curators.service import CuratorsService
from agentworkmemory.services.sessions.service import SessionsService
from agentworkmemory.services.sessions.store import SessionsStore
from agentworkmemory.services.translations import (
    Locale,
    TranslationService,
    TranslationStatus,
)
from agentworkmemory.services.translations.service import page_locale, source_digest
from agentworkmemory.services.vault import VaultService
from agentworkmemory.services.wiki import WikiCatalogService
from agentworkmemory.settings import AgentWorkMemoryConfig
from agentworkmemory.workflows.translate import (
    TranslateWikiPages,
    TranslateWikiWorkflow,
)


def test_translation_service_resolves_original_current_and_stale_pages(
    tmp_path: Path,
):
    vault, translations = translation_services(tmp_path)
    canonical = write_canonical(vault, language="en")

    original = translations.resolve(canonical, Locale.EN)
    missing = translations.resolve(canonical, Locale.KO)

    assert original.status is TranslationStatus.ORIGINAL
    assert original.resolved_locale is Locale.EN
    assert missing.status is TranslationStatus.MISSING
    assert missing.resolved_locale is Locale.EN

    write_translation(vault, canonical, source_digest(original.body))
    current = translations.resolve(canonical, Locale.KO)
    assert current.status is TranslationStatus.CURRENT
    assert current.resolved_locale is Locale.KO
    assert current.title == "중앙 작성기"

    target = vault.require_path() / canonical
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            "One writer owns updates.",
            "One writer owns every update.",
        ),
        encoding="utf-8",
    )
    stale = translations.resolve(canonical, Locale.KO)
    assert stale.status is TranslationStatus.STALE
    assert stale.resolved_locale is Locale.KO


def test_invalid_translation_falls_back_to_the_original(tmp_path: Path):
    vault, translations = translation_services(tmp_path)
    canonical = write_canonical(vault, language="en")
    target = vault.require_path() / "translations/ko" / canonical
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\ntranslation_of: decisions/other.md\nlanguage: ko\n"
        f"source_digest: {'0' * 64}\n---\n# 잘못된 번역\n",
        encoding="utf-8",
    )

    resolved = translations.resolve(canonical, Locale.KO)

    assert resolved.status is TranslationStatus.INVALID
    assert resolved.resolved_locale is Locale.EN
    assert resolved.title == "Central writer"


def test_legacy_locale_inference_ignores_a_minor_link_alias_language():
    english_body = (
        "Public drafts omit employer details and keep only the functional "
        "description needed by the essay. " * 8
        + "Project: [[projects/employment-essay|국민내일배움카드 취업 원고]]"
    )
    korean_body = (
        "이 문서는 시스템의 현재 상태와 다음 작업을 한국어로 설명합니다. " * 8
        + "Runtime: Codex and Ollama"
    )

    assert page_locale(None, "Generalize employer details", english_body) is Locale.EN
    assert page_locale(None, "시스템 운영 상태", korean_body) is Locale.KO


def test_translation_files_are_not_wiki_graph_pages(tmp_path: Path):
    vault, translations = translation_services(tmp_path)
    canonical = write_canonical(vault, language="en")
    original = translations.resolve(canonical, Locale.EN)
    write_translation(vault, canonical, source_digest(original.body))
    sessions = SessionsService(SessionsStore(tmp_path / "state/awm.db"))
    wiki = WikiCatalogService(vault, sessions)

    pages = wiki.pages()

    assert [page.path.as_posix() for page in pages] == [canonical.as_posix()]


def test_translation_workflow_writes_only_a_derived_sidecar(tmp_path: Path):
    vault, translations = translation_services(tmp_path)
    canonical = write_canonical(vault, language="en")
    original = (vault.require_path() / canonical).read_text(encoding="utf-8")
    sessions = SessionsService(SessionsStore(tmp_path / "state/awm.db"))
    wiki = WikiCatalogService(vault, sessions)
    workflow = TranslateWikiWorkflow(
        CuratorsService((FakeTranslator(),)),
        vault,
        wiki,
        translations,
    )

    changed = workflow.run(
        TranslateWikiPages(
            paths=(canonical,),
            locale=Locale.KO,
            runtime="codex",
            content_access=ContentAccess.SELECTED_REMOTE,
        )
    )

    assert changed == (Path("translations/ko") / canonical,)
    assert (vault.require_path() / canonical).read_text(encoding="utf-8") == original
    resolved = translations.resolve(canonical, Locale.KO)
    assert resolved.status is TranslationStatus.CURRENT
    assert "하나의 작성기" in resolved.body


class FakeTranslator:
    runtime = "codex"

    def check(self) -> CuratorReadiness:
        return CuratorReadiness(
            runtime=self.runtime,
            available=True,
            message="ready",
        )

    def run(self, request: CuratorRunRequest) -> CuratorRunResult:
        target = next(request.vault_path.rglob("*.md"))
        raw = target.read_text(encoding="utf-8")
        frontmatter = raw.split("---", 2)[1]
        target.write_text(
            f"---{frontmatter}---\n# 중앙 작성기\n\n"
            "하나의 작성기가 갱신을 담당합니다.\n",
            encoding="utf-8",
        )
        return CuratorRunResult(
            runtime=self.runtime,
            status=CuratorRunStatus.SUCCEEDED,
            output_text="translated",
        )


def translation_services(
    tmp_path: Path,
) -> tuple[VaultService, TranslationService]:
    root = tmp_path / "vault"
    root.mkdir()
    vault = VaultService(
        AgentWorkMemoryConfig(
            state_dir=tmp_path / "state",
            vault_path=root,
        )
    )
    return vault, TranslationService(vault)


def write_canonical(vault: VaultService, *, language: str) -> Path:
    relative = Path("decisions/central-writer.md")
    target = vault.require_path() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\n"
        f"language: {language}\n"
        "short_title_ko: 중앙 작성기\n"
        "short_title_en: Central writer\n"
        "---\n"
        "# Central writer\n\n"
        "One writer owns updates.\n",
        encoding="utf-8",
    )
    return relative


def write_translation(
    vault: VaultService,
    canonical: Path,
    digest: str,
) -> None:
    target = vault.require_path() / "translations/ko" / canonical
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\n"
        f"translation_of: {canonical.as_posix()}\n"
        "language: ko\n"
        f"source_digest: {digest}\n"
        "---\n"
        "# 중앙 작성기\n\n"
        "하나의 작성기가 갱신을 담당합니다.\n",
        encoding="utf-8",
    )
