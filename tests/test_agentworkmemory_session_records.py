from pathlib import Path

from agentworkmemory.app import create_app
from agentworkmemory.services.vault import session_records
from agentworkmemory.settings import AgentWorkMemoryConfig


def test_large_session_record_uses_bounded_numbered_parts_and_cleans_them(
    tmp_path: Path,
    monkeypatch,
):
    app = create_app(
        AgentWorkMemoryConfig(
            state_dir=tmp_path / "state",
            vault_path=None,
        )
    )
    vault = app.vault.initialize(tmp_path / "vault")
    session = app.sessions.add_manual_note(
        "가" * 50_000,
        title="Large retained session",
    )
    events = app.sessions.events(session.session_id)
    monkeypatch.setattr(session_records, "SESSION_RECORD_PART_BYTES", 12_000)

    index = app.vault.refresh_session(session, events)

    parts_dir = index.with_suffix("")
    parts = tuple(sorted(parts_dir.glob("part-*.md")))
    assert index == (
        vault / "inbox" / "agent-sessions" / f"manual-{session.session_id}.md"
    )
    assert len(parts) > 1
    assert [path.name for path in parts] == [
        f"part-{number:03d}.md" for number in range(1, len(parts) + 1)
    ]
    assert all(path.stat().st_size <= 12_000 for path in parts)
    assert "## Record parts" in index.read_text(encoding="utf-8")
    rendered_parts = "\n".join(path.read_text(encoding="utf-8") for path in parts)
    assert rendered_parts.count("가") == 50_000
    assert "continuation" in rendered_parts

    small = events[0].model_copy(update={"content": "small retained event"})
    app.vault.refresh_session(session, (small,))

    assert not parts_dir.exists()
    assert "small retained event" in index.read_text(encoding="utf-8")
    assert "## Record parts" not in index.read_text(encoding="utf-8")
