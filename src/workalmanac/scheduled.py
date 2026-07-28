import argparse
import sys
import traceback
from collections.abc import Sequence
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path

from workalmanac.cli import main as cli_main

MAX_SCHEDULED_LOG_BYTES = 5 * 1024 * 1024


def main(argv: Sequence[str] | None = None) -> int:
    arguments = tuple(argv if argv is not None else sys.argv[1:])
    state_dir = scheduled_state_dir(arguments)
    log_path = scheduled_log_path(state_dir, arguments)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rotate_log(log_path)
    with (
        log_path.open("a", encoding="utf-8", buffering=1) as stream,
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
        return exit_code


def scheduled_state_dir(arguments: Sequence[str]) -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--state-dir", type=Path, required=True)
    parsed, _ = parser.parse_known_args(arguments)
    return parsed.state_dir.expanduser().resolve()


def scheduled_log_path(state_dir: Path, arguments: Sequence[str]) -> Path:
    task = "auto-distill" if "auto-distill" in arguments else "sync"
    return state_dir / "logs" / f"scheduled-{task}.log"


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
