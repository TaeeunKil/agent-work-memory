from pathlib import Path

import pytest

from workalmanac.app import create_app
from workalmanac.cli import main
from workalmanac.services.curators.models import ContentAccess
from workalmanac.settings import WorkAlmanacConfig
from workalmanac.workflows.distill.prompt import distill_prompt


def test_init_builds_obsidian_home_and_category_indexes(
    tmp_path: Path,
):
    state = tmp_path / "state"
    vault = tmp_path / "vault"

    assert main(("--state-dir", str(state), "init", str(vault))) == 0

    home = (vault / "Home.md").read_text(encoding="utf-8")
    assert "workalmanac_managed: true" in home
    assert "[[projects/_index|Projects]] · 0" in home
    assert "[[inbox/agent-sessions|All retained agent sessions]]" in home
    for category in (
        "projects",
        "decisions",
        "problems",
        "procedures",
        "systems",
        "unfinished",
    ):
        assert (vault / category / "_index.md").is_file()


def test_catalog_generates_sources_backlinks_and_stable_indexes(tmp_path: Path):
    app = wiki_app(tmp_path)
    vault = app.vault.initialize(tmp_path / "vault")
    session = app.sessions.add_manual_note(
        "Keep a single Markdown writer.",
        title="Central writer discussion",
    )
    app.vault.refresh_session(session, app.sessions.events(session.session_id))
    (vault / "decisions" / "central-writer.md").write_text(
        f"""---
tags:
  - architecture
sources:
  - id: central-writer-session
    type: conversation
    session_id: {session.session_id}
---
# Central writer

Use one writer for durable Markdown.
""",
        encoding="utf-8",
    )
    (vault / "projects" / "work-almanac.md").write_text(
        """# Work Almanac project

The project follows [[decisions/central-writer|Central writer]].
""",
        encoding="utf-8",
    )

    first = app.wiki.refresh()
    second = app.wiki.refresh()

    assert Path("Home.md") in first
    assert second == ()
    decision_index = (vault / "decisions" / "_index.md").read_text(encoding="utf-8")
    assert "[[decisions/central-writer|Central writer]]" in decision_index
    assert "[[projects/work-almanac|Work Almanac project]]" in decision_index
    assert (
        f"[[inbox/agent-sessions/manual-{session.session_id}"
        "|Central writer discussion · manual]]"
    ) in decision_index
    assert "Tags: architecture" in decision_index
    home = (vault / "Home.md").read_text(encoding="utf-8")
    assert "[[decisions/_index|Decisions]] · 1" in home
    assert "[[projects/_index|Projects]] · 1" in home
    assert len(app.wiki.pages()) == 2


def test_managed_indexes_are_not_curator_writable(tmp_path: Path):
    app = wiki_app(tmp_path)
    app.vault.initialize(tmp_path / "vault")
    app.wiki.refresh()

    with app.vault.curator_workspace() as (workspace, snapshot, _):
        (workspace / "decisions" / "_index.md").write_text(
            "# Curator replaced the index\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="forbidden Vault path"):
            app.vault.validate_distill_changes(snapshot)


def test_distill_prompt_supplies_navigable_session_link(tmp_path: Path):
    app = wiki_app(tmp_path)
    app.vault.initialize(tmp_path / "vault")
    session = app.sessions.add_manual_note(
        "Use Obsidian links for evidence.",
        title="Evidence navigation",
    )

    prompt = distill_prompt(
        ((session, app.sessions.events(session.session_id)),),
        ContentAccess.SELECTED_LOCAL,
    )

    assert (
        f"[[inbox/agent-sessions/manual-{session.session_id}|Evidence navigation]]"
    ) in prompt
    assert "Never edit README.md, Home.md, _index.md" in prompt


def test_catalog_skips_invalid_manual_markdown_without_breaking_sync(
    tmp_path: Path,
):
    app = wiki_app(tmp_path)
    vault = app.vault.initialize(tmp_path / "vault")
    invalid = vault / "projects" / "invalid.md"
    invalid.write_bytes(b"\xff\xfe")

    changed = app.wiki.refresh()

    assert Path("Home.md") in changed
    assert app.wiki.pages() == ()


def wiki_app(tmp_path: Path):
    return create_app(
        WorkAlmanacConfig(
            state_dir=tmp_path / "state",
            vault_path=None,
        )
    )
