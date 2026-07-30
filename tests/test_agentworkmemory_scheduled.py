from pathlib import Path

from agentworkmemory import scheduled
from agentworkmemory.services.activity import ActivityService, ActivityStatus


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
    activity = ActivityService(state / "activity").list()
    assert len(activity) == 1
    assert activity[0].task == "auto-distill"
    assert activity[0].status is ActivityStatus.SUCCEEDED
    assert activity[0].summary == "ran run"
    assert "ran run" in activity[0].log_lines


def test_scheduled_runner_rotates_bounded_logs(tmp_path: Path, monkeypatch):
    log = tmp_path / "scheduled-sync.log"
    log.write_text("old log", encoding="utf-8")
    monkeypatch.setattr(scheduled, "MAX_SCHEDULED_LOG_BYTES", 1)

    scheduled.rotate_log(log)

    assert not log.exists()
    assert log.with_suffix(".log.1").read_text(encoding="utf-8") == "old log"


def test_scheduled_runner_records_skipped_and_failed_activity(
    tmp_path: Path,
    monkeypatch,
):
    state = tmp_path / "state"

    def skipped_cli(_arguments):
        print(
            "Automatic distillation skipped because sync or another "
            "distillation is running."
        )
        return 0

    monkeypatch.setattr(scheduled, "cli_main", skipped_cli)
    assert scheduled.main(("--state-dir", str(state), "auto-distill", "run")) == 0

    def failed_cli(_arguments):
        raise RuntimeError("scheduled probe failed")

    monkeypatch.setattr(scheduled, "cli_main", failed_cli)
    assert scheduled.main(("--state-dir", str(state), "sync")) == 1

    activity = ActivityService(state / "activity").list()
    assert activity[0].status is ActivityStatus.FAILED
    assert "RuntimeError: scheduled probe failed" in activity[0].log_lines
    assert activity[1].status is ActivityStatus.SKIPPED
    assert activity[1].summary == "Waiting for synchronization to finish"
