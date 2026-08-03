import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

import yaml

from agentworkmemory.services.frontmatter import split_frontmatter
from agentworkmemory.services.translations.models import (
    Locale,
    PageRepresentation,
    TranslationStatus,
)
from agentworkmemory.services.vault.service import VaultService, ensure_inside

TRANSLATIONS_ROOT = Path("translations")
HANGUL = re.compile(r"[\uac00-\ud7a3]")
LATIN = re.compile(r"[A-Za-z]")


class TranslationService:
    def __init__(self, vault: VaultService):
        self.vault = vault

    def resolve(
        self,
        canonical_path: Path,
        requested_locale: Locale | None = None,
    ) -> PageRepresentation:
        root = self.vault.require_path().resolve()
        canonical = safe_canonical_path(canonical_path)
        source = (root / canonical).resolve()
        ensure_inside(root, source)
        if source.is_symlink() or not source.is_file():
            raise KeyError(f"unknown Wiki page: {canonical}")

        raw = source.read_text(encoding="utf-8")
        metadata, body = split_frontmatter(raw)
        title = markdown_title(canonical, body)
        original_locale = page_locale(metadata.get("language"), title, body)
        requested = requested_locale or original_locale
        if requested is original_locale:
            return PageRepresentation(
                canonical_path=canonical,
                requested_locale=requested,
                resolved_locale=original_locale,
                original_locale=original_locale,
                status=TranslationStatus.ORIGINAL,
                title=title,
                body=body,
            )

        translated = (root / translation_path(requested, canonical)).resolve()
        ensure_inside(root, translated)
        if translated.is_symlink() or not translated.is_file():
            return fallback_representation(
                canonical,
                requested,
                original_locale,
                title,
                body,
                TranslationStatus.MISSING,
            )
        try:
            translated_raw = translated.read_text(encoding="utf-8")
            translated_metadata, translated_body = split_frontmatter(translated_raw)
            validate_translation_metadata(
                translated_metadata,
                canonical=canonical,
                locale=requested,
            )
        except (OSError, UnicodeError, ValueError, yaml.YAMLError):
            return fallback_representation(
                canonical,
                requested,
                original_locale,
                title,
                body,
                TranslationStatus.INVALID,
            )
        status = (
            TranslationStatus.CURRENT
            if translated_metadata["source_digest"] == source_digest(body)
            else TranslationStatus.STALE
        )
        return PageRepresentation(
            canonical_path=canonical,
            requested_locale=requested,
            resolved_locale=requested,
            original_locale=original_locale,
            status=status,
            title=markdown_title(translated, translated_body),
            body=translated_body,
        )

    def write(
        self,
        canonical_path: Path,
        locale: Locale,
        translated_body: str,
        *,
        translator: str,
    ) -> Path:
        canonical = safe_canonical_path(canonical_path)
        original = self.resolve(canonical)
        if locale is original.original_locale:
            raise ValueError("a translation must differ from the original language")
        if not has_h1(translated_body):
            raise ValueError("translated Markdown needs an H1 heading and body")
        root = self.vault.require_path().resolve()
        target_relative = translation_path(locale, canonical)
        target = (root / target_relative).resolve()
        ensure_inside(root, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        content = render_translation(
            canonical,
            locale,
            source_digest(original.body),
            translated_body,
            translator=translator,
        )
        temporary = target.with_suffix(f"{target.suffix}.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
        return target_relative


def safe_canonical_path(value: Path) -> Path:
    if value.is_absolute() or PureWindowsPath(str(value)).is_absolute():
        raise ValueError("canonical Wiki path must be relative")
    normalized = Path(str(value).replace("\\", "/"))
    if not normalized.parts or ".." in normalized.parts:
        raise ValueError("canonical Wiki path is invalid")
    if normalized.parts[0] == TRANSLATIONS_ROOT.name:
        raise ValueError("translation paths are not canonical Wiki paths")
    return normalized


def translation_path(locale: Locale, canonical_path: Path) -> Path:
    canonical = safe_canonical_path(canonical_path)
    return TRANSLATIONS_ROOT / locale.value / canonical


def source_digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def page_locale(value: object, title: str, body: str) -> Locale:
    if isinstance(value, str):
        try:
            return Locale(value.strip().lower())
        except ValueError:
            pass
    sample = f"{title}\n{body[:8000]}"
    hangul_count = len(HANGUL.findall(sample))
    latin_count = len(LATIN.findall(sample))
    korean_dominates = hangul_count > 0 and (
        hangul_count >= latin_count * 0.15
        or (hangul_count >= 10 and latin_count < 50)
    )
    return Locale.KO if korean_dominates else Locale.EN


def validate_translation_metadata(
    metadata: dict[str, object],
    *,
    canonical: Path,
    locale: Locale,
) -> None:
    if metadata.get("translation_of") != canonical.as_posix():
        raise ValueError("translation_of does not match the canonical page")
    if metadata.get("language") != locale.value:
        raise ValueError("translation language does not match its path")
    digest = metadata.get("source_digest")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("translation source_digest is invalid")


def fallback_representation(
    canonical: Path,
    requested: Locale,
    original: Locale,
    title: str,
    body: str,
    status: TranslationStatus,
) -> PageRepresentation:
    return PageRepresentation(
        canonical_path=canonical,
        requested_locale=requested,
        resolved_locale=original,
        original_locale=original,
        status=status,
        title=title,
        body=body,
    )


def markdown_title(path: Path, body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# ") and line[2:].strip():
            return line[2:].strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


def has_h1(body: str) -> bool:
    return any(
        line.startswith("# ") and line[2:].strip()
        for line in body.splitlines()
    )


def render_translation(
    canonical: Path,
    locale: Locale,
    digest: str,
    body: str,
    *,
    translator: str,
) -> str:
    metadata = {
        "translation_of": canonical.as_posix(),
        "language": locale.value,
        "source_digest": digest,
        "translated_at": datetime.now(UTC).isoformat(),
        "translator": translator,
    }
    frontmatter = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        sort_keys=False,
    ).rstrip()
    return f"---\n{frontmatter}\n---\n{body.lstrip()}".rstrip() + "\n"
