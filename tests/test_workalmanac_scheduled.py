from pathlib import Path

from workalmanac import scheduled


def test_scheduled_runner_redirects_output_to_a_private_task_log(
    tmp_path: Path,
    monkeypatch,
):
    state = tmp_path / "Private State"

    def fake_cli(arguments):
        print(f"ran {arguments[-1]}")
        return 0

    monkeypatch.setattr(scheduled, "cli_main", fake_cli)

    assert (
        scheduled.main(("--state-dir", str(state), "auto-distill", "run"))
        == 0
    )

    log = state / "logs" / "scheduled-auto-distill.log"
    content = log.read_text(encoding="utf-8")
    assert "scheduled run started" in content
    assert "ran run" in content
    assert "scheduled run finished: exit 0" in content


def test_scheduled_runner_rotates_bounded_logs(tmp_path: Path, monkeypatch):
    log = tmp_path / "scheduled-sync.log"
    log.write_text("old log", encoding="utf-8")
    monkeypatch.setattr(scheduled, "MAX_SCHEDULED_LOG_BYTES", 1)

    scheduled.rotate_log(log)

    assert not log.exists()
    assert log.with_suffix(".log.1").read_text(encoding="utf-8") == "old log"
