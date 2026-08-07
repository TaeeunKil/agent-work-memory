from agentworkmemory.services.frontmatter import (
    normalize_durable_markdown,
    peel_frontmatter_blocks,
)
from agentworkmemory.services.vault.service import preserve_existing_frontmatter


def test_normalize_collapses_stacked_frontmatter_and_crlf():
    raw = (
        "---\n"
        "short_title_ko: 제목\n"
        "short_title_en: Title\n"
        "language: en\n"
        "sources:\n"
        "- session_id: ses_one\n"
        "  provider: codex\n"
        "---\n"
        "---\r\n"
        "short_title_ko: 제목\r\n"
        "short_title_en: Title\r\n"
        "language: en\r\n"
        "sources:\r\n"
        "- session_id: ses_one\r\n"
        "  provider: codex\r\n"
        "- session_id: ses_two\r\n"
        "  provider: codex\r\n"
        "---\r\n"
        "\r\n"
        "# Title\r\n"
        "\r\n"
        "Body.\r\n"
    )

    cleaned = normalize_durable_markdown(raw)
    metadata, body = peel_frontmatter_blocks(cleaned)

    assert cleaned.count("---\n") == 2
    assert "\r" not in cleaned
    assert metadata["short_title_ko"] == "제목"
    assert metadata["sources"] == [
        {"session_id": "ses_one", "provider": "codex"},
        {"session_id": "ses_two", "provider": "codex"},
    ]
    assert body.startswith("# Title\n")
    assert "Body." in body


def test_preserve_frontmatter_does_not_restack_blocks():
    original = (
        "---\n"
        "short_title_ko: 안정\n"
        "short_title_en: Stable\n"
        "language: en\n"
        "sources:\n"
        "- session_id: ses_original\n"
        "  provider: codex\n"
        "---\n"
        "# Stable\n"
    )
    current = (
        "---\n"
        "short_title_en: Revised\n"
        "language: en\n"
        "---\n"
        "---\n"
        "short_title_en: Revised\n"
        "language: en\n"
        "---\n"
        "# Revised\n"
        "\n"
        "Curator body.\n"
    )

    repaired = preserve_existing_frontmatter(original, current)

    assert repaired.count("short_title_ko:") == 1
    assert repaired.count("short_title_en:") == 1
    assert "short_title_ko: 안정" in repaired
    assert "short_title_en: Revised" in repaired
    assert repaired.count("---\n") == 2
    assert repaired.endswith("Curator body.\n")
