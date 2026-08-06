# Slice 188: Drain the remaining distillation backlog

## Intent

Let the owner resize an existing automatic-distillation grant for a known
backlog without reinstalling the scheduler or resetting its reservation
counter. This supports a bounded backlog drain while keeping the selected
remote-content scope and expiry visible.

## Shape

```text
awm auto-distill configure --limit N --max-total N
  -> AutoDistillationService.configure(...)
  -> preserve installed_at, expires_at, content_access, sessions_reserved
  -> scheduled task continues reading the same state pointer
```

The CLI keeps the existing model and reasoning effort controls. `max-total`
must remain within the model's finite 1,000-session ceiling and cannot be
lower than sessions already reserved. The per-run limit remains 1–20.

## Verification

- Configuration updates preserve the current standing grant and scheduler.
- A backlog-sized grant can cover all currently pending sessions without an
  unbounded permission.
- Existing AWM tests, Ruff, JavaScript syntax, and diff checks pass.
