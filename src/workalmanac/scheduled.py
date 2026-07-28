import argparse
import os
import sys
import traceback
from collections.abc import Sequence
from contextlib import redirect_stderr, redirect_stdout, suppress
from datetime import UTC, datetime
from io import TextIOBase
from pathlib import Path

from workalmanac.cli import main as cli_main
from workalmanac.services.activity import ActivityRun, ActivityService, ActivityTask

MAX_SCHEDULED_LOG_BYTES = 5 * 1024 * 1024


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(argv if argv is not None else sys.argv[1:])
    state_dir = scheduled_state_dir(arguments)
    log_path = scheduled_log_path(state_dir, arguments)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rotate_log(log_path)
    activity = ActivityService(state_dir / "activity")
    run = begin_activity(activity, scheduled_task(arguments))
    with (
        log_path.open("a", encoding="utf-8", buffering=1) as log_stream,
        ActivityLogStream(log_stream, activity, run) as stream,
        redirect_stdout(stream),
        redirect_stderr(stream),
    ):
        print(f"[{timestamp()}] scheduled run started")
        try:
            exit_code = cli_main(arguments)
        except Exception:
            traceback.print_exc()
            exit_code = 1
        print(f"[{timestamp()}] scheduled run finished: exit {exit_code}")
        finish_activity(activity, run, exit_code)
        return exit_code


def scheduled_state_dir(arguments: Sequence[str]) -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--state-dir", type=Path, required=True)
    parsed, _ = parser.parse_known_args(arguments)
    return parsed.state_dir.expanduser().resolve()


def scheduled_log_path(state_dir: Path, arguments: Sequence[str]) -> Path:
    return state_dir / "logs" / f"scheduled-{scheduled_task(arguments).value}.log"


def scheduled_task(arguments: Sequence[str]) -> ActivityTask:
    if "auto-distill" in arguments:
        return ActivityTask.AUTO_DISTILL
    return ActivityTask.SYNC


def begin_activity(
    service: ActivityService,
    task: ActivityTask,
) -> ActivityRun | None:
    try:
        return service.begin(task, process_id=os.getpid())
    except OSError:
        return None


def finish_activity(
    service: ActivityService,
    run: ActivityRun | None,
    exit_code: int,
) -> None:
    if run is None:
        return
    try:
        service.finish(run, exit_code=exit_code)
    except OSError:
        return


class ActivityLogStream(TextIOBase):
    def __init__(
        self,
        stream: TextIOBase,
        service: ActivityService,
        run: ActivityRun | None,
    ):
        self.stream = stream
        self.service = service
        self.run = run

    def write(self, value: str) -> int:
        written = self.stream.write(value)
        self.stream.flush()
        if self.run is not None:
            with suppress(OSError):
                self.run = self.service.append_log(self.run, value)
        return written

    def flush(self) -> None:
        self.stream.flush()

    def close(self) -> None:
        self.flush()


def rotate_log(path: Path) -> None:
    try:
        if path.stat().st_size < MAX_SCHEDULED_LOG_BYTES:
            return
        backup = path.with_suffix(path.suffix + ".1")
        backup.unlink(missing_ok=True)
        path.replace(backup)
    except OSError:
        return


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
