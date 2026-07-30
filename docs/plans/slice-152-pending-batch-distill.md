# Slice 152: pending-session batch distillation

## Outcome

Users can promote the newest captured, not-yet-distilled sessions without
copying opaque session IDs by hand:

```powershell
wa distill --pending --limit 3 --using codex --allow-remote-content
```

## Contract

- Explicit session IDs remain supported.
- `--pending` and explicit IDs cannot be combined.
- `--limit` is valid only with `--pending`, defaults to 3, and must be between
  1 and 20.
- Pending means `content_captured` is true and `distilled_at` is absent.
- Selection uses the existing newest-first session ordering.
- The curator evidence budget is divided across selected sessions so one long
  transcript cannot consume the entire batch context.
- An empty pending queue exits successfully without invoking a curator.
- The command prints the selected IDs before model execution.
- Existing content-access grants remain mandatory and unchanged.

## Architecture

`SessionsService` owns the pending-session query. The CLI maps the user's
selection mode into concrete IDs and then calls the unchanged
`DistillSessionsWorkflow`. This keeps model execution, Vault validation,
rollback, receipts, and distilled-state transitions on the existing path.

Automatic scheduled distillation is deliberately separate: it requires a
persisted standing content grant, retry policy, and usage budget.

## Verification

- pending selection excludes metadata-only and already-distilled sessions;
- default and explicit limits select newest-first;
- conflicting and invalid CLI inputs fail before curator execution;
- empty pending queues are no-ops;
- explicit-ID behavior remains compatible;
- Agent Work Memory regression tests and Ruff pass.
