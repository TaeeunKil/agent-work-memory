# Fixes for slice 154 review

## Intent

Make the Activity summary strip answer both operational questions without
opening a row: what is running now, and which installed task runs next.

## Must-fix

- Expose the OS scheduler's actual next-run timestamp for automatic transcript
  sync and automatic Wiki distillation.
- Present the earliest installed schedule in the first Activity summary line
  beside the running count.
- Keep scheduled run history below the summary; do not represent a future
  schedule as a completed or running activity record.
- Preserve the live two-second activity refresh without invoking an OS process
  on every poll.

## Design

Scheduler adapters own the external scheduler query and normalize it to an
optional timezone-aware `datetime`. The two automation services expose that
fact through their existing typed status models. The viewer adds a dedicated
schedule endpoint, fetched independently from the fast activity ledger.

```python
sync = workalmanac.automation.status()
distill = workalmanac.auto_distillation.status()
next_schedule = earliest_installed(sync, distill)
```

Windows reads `Get-ScheduledTaskInfo` as JSON rather than scraping localized
human-readable `schtasks` output. Unsupported platforms return no next run.

## Files

- Extend automation and auto-distillation scheduler ports, status models, and
  adapters with `next_run_at`.
- Add `/api/schedules` to the local viewer.
- Update Activity JavaScript and CSS to render the next task and timestamp in
  the first summary strip.
- Add focused adapter, service/API, and frontend contract tests.

## Out of scope

- Editing schedules from the viewer.
- Predicting uninstalled schedules from saved settings.
- Replacing the Windows Task Scheduler or changing its cadence.

## Verification

- `uv run pytest tests/test_workalmanac_sync.py tests/test_workalmanac_auto_distill.py tests/test_workalmanac_viewer.py`
- `uv run pytest tests/test_workalmanac_scheduled.py`
- `uv run ruff check src/workalmanac tests/test_workalmanac_sync.py tests/test_workalmanac_auto_distill.py tests/test_workalmanac_viewer.py`
- JavaScript syntax check and desktop/mobile viewer inspection.

## Read before coding

- `MANUAL.md`
- `docs/plans/slice-153-automatic-distillation.md`
- `src/workalmanac/services/automation/`
- `src/workalmanac/services/auto_distillation/`
- `src/workalmanac/viewer/`
