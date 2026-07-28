# Slice 156: Visible synchronization progress and distillation unblock

## Outcome

AWM reports coarse synchronization progress while it is running, so the
Activity inspector distinguishes active work from a stalled process. Automatic
Wiki distillation no longer predictably collides with transcript sync on the
current machine.

## Scope

- Add an optional progress-reporting seam to synchronization workflows.
- Report local provider collection, each SSH host, search indexing, and final
  completion without producing one log line per session.
- Connect CLI synchronization output to the existing scheduled activity log.
- Keep viewer-triggered synchronization behavior compatible.
- Change the current machine's transcript sync cadence from five to fifteen
  minutes.
- On Windows Codex CLI, pre-create a user-owned JSON handoff file. Codex writes
  proposed paths and complete Markdown content into that existing file, then
  AWM validates paths and creates the Wiki files as the parent user.
- Run one foreground automatic distillation and verify a durable Wiki page.

## Architecture

Workflows accept an optional callable reporter. They remain independent of the
terminal and scheduler:

```text
awm sync / scheduled runner
          |
          | print callback
          v
Sync workflow -> Collect workflow -> provider progress
       |
       +--------> Remote workflow -> SSH host progress
       |
       +--------> search refresh
```

The CLI passes `print`; other adapters may omit the reporter. The scheduled
runner already captures stdout in `ActivityLogStream`, so every reported stage
becomes visible through the Activity API and its existing two-second polling.

Progress remains intentionally coarse to bound activity-file writes:

1. local transcript collection;
2. each configured provider;
3. each registered SSH host;
4. search index refresh;
5. completion.

## Scheduling

The current five-minute sync usually takes about six minutes, while hourly
distillation starts on the same minute. This guarantees overlap. Reinstall the
existing sync schedule at a fifteen-minute cadence after code verification,
preserving its providers, home path, and content setting. The existing
auto-distill grant and hourly schedule remain in place.

## Tests

- A sync reporter receives stage messages in execution order.
- Collection reports provider start and completion summaries.
- Remote collection reports host ordinal, success, and failure.
- Existing callers without a reporter remain compatible.
- Run the focused Agent Work Memory suite and Ruff.
- Run JavaScript syntax checking.
- Inspect the real schedules and activity log after reconfiguration.
- Run foreground auto-distill and verify its receipt plus a durable Wiki file.

## Out of scope

- Streaming subprocess output from Codex itself.
- Per-session logging.
- Replacing Activity polling with SSE.
- Changing distillation grants or remote-content policy.
