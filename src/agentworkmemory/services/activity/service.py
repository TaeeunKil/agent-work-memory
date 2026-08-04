from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from filelock import FileLock

from agentworkmemory.services.activity.models import (
    ActivityLedger,
    ActivityRun,
    ActivityStatus,
    ActivityTask,
)
from agentworkmemory.services.activity.ports import ActivityProcessProbe

MAX_ACTIVITY_RUNS = 30
MAX_ACTIVITY_LOG_LINES = 80
MAX_ACTIVITY_LINE_LENGTH = 500


class ActivityService:
    def __init__(self, root: Path, process_probe: ActivityProcessProbe):
        self.root = root
        self.process_probe = process_probe

    def begin(
        self,
        task: ActivityTask,
        *,
        process_id: int,
        started_at: datetime | None = None,
    ) -> ActivityRun:
        run = ActivityRun(
            activity_id=f"act_{uuid4().hex}",
            task=task,
            status=ActivityStatus.RUNNING,
            started_at=started_at or datetime.now(UTC),
            process_id=process_id,
            summary=running_summary(task),
        )
        with self.lock(task):
            ledger = reconciled_ledger(
                self.load(task),
                self.process_probe,
                datetime.now(UTC),
            )
            self.save(
                task,
                ActivityLedger(runs=(run, *ledger.runs)[:MAX_ACTIVITY_RUNS]),
            )
        return run

    def append_log(self, run: ActivityRun, value: str) -> ActivityRun:
        lines = normalized_log_lines(value)
        if not lines:
            return run
        with self.lock(run.task):
            ledger = self.load(run.task)
            current = ledger_run(ledger, run.activity_id) or run
            updated = current.model_copy(
                update={
                    "summary": activity_summary(lines[-1], current.task),
                    "log_lines": (
                        *current.log_lines,
                        *lines,
                    )[-MAX_ACTIVITY_LOG_LINES:],
                }
            )
            self.save(run.task, replace_ledger_run(ledger, updated))
            return updated

    def finish(
        self,
        run: ActivityRun,
        *,
        exit_code: int,
        finished_at: datetime | None = None,
    ) -> ActivityRun:
        with self.lock(run.task):
            ledger = self.load(run.task)
            current = ledger_run(ledger, run.activity_id) or run
            status = completed_status(exit_code, current.log_lines)
            updated = current.model_copy(
                update={
                    "status": status,
                    "finished_at": finished_at or datetime.now(UTC),
                    "exit_code": exit_code,
                    "summary": completion_summary(status, current),
                }
            )
            self.save(run.task, replace_ledger_run(ledger, updated))
            return updated

    def list(self, limit: int = 60) -> tuple[ActivityRun, ...]:
        runs = tuple(
            run
            for task in ActivityTask
            for run in self.reconcile(task).runs
        )
        return tuple(
            sorted(runs, key=lambda run: run.started_at, reverse=True)[:limit]
        )

    def reconcile(self, task: ActivityTask) -> ActivityLedger:
        with self.lock(task):
            ledger = self.load(task)
            reconciled = reconciled_ledger(
                ledger,
                self.process_probe,
                datetime.now(UTC),
            )
            if reconciled != ledger:
                self.save(task, reconciled)
            return reconciled

    def load(self, task: ActivityTask) -> ActivityLedger:
        path = self.path(task)
        if not path.is_file():
            return ActivityLedger()
        try:
            return ActivityLedger.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ActivityLedger()

    def save(self, task: ActivityTask, ledger: ActivityLedger) -> None:
        path = self.path(task)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            ledger.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def path(self, task: ActivityTask) -> Path:
        return self.root / f"{task.value}.json"

    def lock(self, task: ActivityTask) -> FileLock:
        self.root.mkdir(parents=True, exist_ok=True)
        return FileLock(self.root / f"{task.value}.lock")


def normalized_log_lines(value: str) -> tuple[str, ...]:
    return tuple(
        line.strip()[:MAX_ACTIVITY_LINE_LENGTH]
        for line in value.splitlines()
        if line.strip()
    )


def activity_summary(line: str, task: ActivityTask) -> str:
    lowered = line.casefold()
    if "scheduled run started" in lowered:
        return running_summary(task)
    if "automatic distillation started" in lowered:
        return "Preparing Codex distillation"
    if "waiting for codex" in lowered:
        return "Waiting for Codex"
    if "codex step" in lowered:
        return line
    if "skipped because sync" in lowered:
        return "Waiting for synchronization to finish"
    if line.startswith("Sync "):
        return line.split(":", 1)[-1].strip()
    return line


def running_summary(task: ActivityTask) -> str:
    if task is ActivityTask.AUTO_DISTILL:
        return "Starting scheduled distillation"
    return "Starting scheduled synchronization"


def completed_status(
    exit_code: int,
    log_lines: tuple[str, ...],
) -> ActivityStatus:
    if exit_code != 0:
        return ActivityStatus.FAILED
    if any("skipped" in line.casefold() for line in log_lines):
        return ActivityStatus.SKIPPED
    return ActivityStatus.SUCCEEDED


def completion_summary(status: ActivityStatus, run: ActivityRun) -> str:
    meaningful = tuple(
        line
        for line in run.log_lines
        if "scheduled run " not in line.casefold()
    )
    if meaningful:
        return activity_summary(meaningful[-1], run.task)
    labels = {
        ActivityStatus.SUCCEEDED: "Completed successfully",
        ActivityStatus.SKIPPED: "Skipped without changes",
        ActivityStatus.FAILED: "Stopped with an error",
        ActivityStatus.RUNNING: running_summary(run.task),
    }
    return labels[status]


def ledger_run(ledger: ActivityLedger, activity_id: str) -> ActivityRun | None:
    return next(
        (run for run in ledger.runs if run.activity_id == activity_id),
        None,
    )


def replace_ledger_run(
    ledger: ActivityLedger,
    updated: ActivityRun,
) -> ActivityLedger:
    found = False
    runs: list[ActivityRun] = []
    for run in ledger.runs:
        if run.activity_id == updated.activity_id:
            runs.append(updated)
            found = True
        else:
            runs.append(run)
    if not found:
        runs.insert(0, updated)
    return ActivityLedger(runs=tuple(runs[:MAX_ACTIVITY_RUNS]))


def reconcile_run(
    run: ActivityRun,
    process_probe: ActivityProcessProbe,
    checked_at: datetime,
) -> ActivityRun:
    if run.status is not ActivityStatus.RUNNING:
        return run
    if process_probe.running(run.process_id, run.started_at):
        return run
    message = "Activity process ended before reporting completion."
    return run.model_copy(
        update={
            "status": ActivityStatus.FAILED,
            "finished_at": checked_at,
            "summary": "Process ended before completion",
            "log_lines": (*run.log_lines, message)[-MAX_ACTIVITY_LOG_LINES:],
        }
    )


def reconciled_ledger(
    ledger: ActivityLedger,
    process_probe: ActivityProcessProbe,
    checked_at: datetime,
) -> ActivityLedger:
    return ActivityLedger(
        runs=tuple(
            reconcile_run(run, process_probe, checked_at)
            for run in ledger.runs
        )
    )
