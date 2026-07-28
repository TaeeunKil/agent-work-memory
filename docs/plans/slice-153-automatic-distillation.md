# Slice 153: opt-in automatic distillation

## Outcome

Users can install a separate scheduled task that promotes a bounded number of
captured, not-yet-distilled sessions:

```powershell
wa auto-distill install \
  --every 60 \
  --limit 1 \
  --using codex \
  --allow-remote-content
```

## Safety contract

- Automatic sync remains evidence-only and never invokes a curator.
- Automatic distillation is a distinct OS task and private settings record.
- Installation requires an explicit standing `selected-local` or
  `selected-remote` content grant; metadata-only automation is rejected.
- Each run processes only captured, not-yet-distilled sessions, newest first.
- `--limit` is constrained to 1 through 20.
- A standing grant expires after seven days and 24 sessions by default.
  `--for-days` (1-30) and `--max-total` (1-100) can narrow or extend those
  explicit bounds.
- An expired or exhausted grant performs no model call until reinstalled.
- The total-session allowance is reserved before curator execution. A failed
  attempt still consumes that allowance so persistence failures cannot create
  unbounded remote sends.
- Local preflight checks run before reservation, so an unavailable runtime or
  unsafe curator workspace does not consume the standing allowance.
- Retained `inbox/` session records are not copied to the curator workspace and
  do not count toward its 50 MiB foreground safety limit. The limit applies to
  the durable Wiki and imported context the curator can actually inspect.
- Foreground runs immediately announce the selected runtime and show elapsed
  time while the curator is working. No percentage is invented because Codex
  does not expose completion progress for a turn.
- Windows scheduled runs use `pythonw.exe`, so periodic sync and distillation
  do not open terminal tabs. Their bounded UTF-8 logs live under
  `<state-dir>/logs/scheduled-sync.log` and `scheduled-auto-distill.log`.
- Windows curation uses the explicitly installed standalone Codex CLI instead
  of the Microsoft Store desktop app executable, avoiding app-sandbox ACLs on
  curator-created Markdown.
- Sync and automatic distillation share the sync lock before either writes to
  SQLite. A colliding run skips without reserving remote-content allowance.
- Curator-created files are retried briefly when Windows still holds a write
  lock. A persistent lock becomes a concise CLI error instead of a traceback.
- The scheduled command contains no session IDs, transcript text, model
  credentials, or content grant. It invokes `wa auto-distill run`, which reads
  private local settings.
- Curator failure uses the existing rollback and body-free receipt path.
- An empty queue is a successful no-op.
- Removing the scheduled task keeps retained sessions and durable Wiki pages.

## Architecture

- `services/auto_distillation/` owns settings, status, persistence, and product
  verbs.
- `services/auto_distillation/ports.py` defines the scheduler adapter.
- `integrations/auto_distillation/` implements Windows Task Scheduler and the
  unsupported-platform boundary.
- `workflows/auto_distill/` selects a bounded pending batch and delegates to
  the existing transactional `DistillSessionsWorkflow`.
- `app.py` remains the composition root and the CLI remains an adapter.

## CLI

```powershell
wa auto-distill install [options]
wa auto-distill status
wa auto-distill run
wa auto-distill remove
```

`run` exists so the OS scheduler and the user can exercise the exact same
workflow.

## Verification

- standing content grant is mandatory;
- install/status/remove persist no transcript bodies;
- scheduled action uses the module entry point and state directory only;
- pending selection respects the configured bound;
- no-op, success, and failure behavior remain isolated;
- Work Almanac regression suite and Ruff pass.
