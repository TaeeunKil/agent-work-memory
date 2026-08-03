from pathlib import Path

from agentworkmemory.services.translations import Locale


def translation_prompt(path: Path, source: Locale, target: Locale) -> str:
    return "\n".join(
        (
            f"Translate the complete Markdown body of {path.as_posix()} from "
            f"{language_name(source)} to {language_name(target)}.",
            "",
            "This is a faithful translation, not a summary or a Wiki curation pass.",
            f"Replace only {path.as_posix()} and do not create any other files.",
            "Preserve the YAML frontmatter exactly; the caller will replace it.",
            "Preserve heading levels, lists, tables, citations, and paragraph order.",
            "Translate prose, headings, and Wiki-link display aliases.",
            "Do not translate Wiki-link targets, URLs, file paths, session IDs, code",
            "blocks, inline code, commands, configuration keys, product names, or",
            "acronyms. Do not add commentary or translator notes.",
            "",
            "Finish with a brief confirmation after replacing the file.",
        )
    )


def language_name(locale: Locale) -> str:
    return {Locale.KO: "Korean", Locale.EN: "English"}[locale]
