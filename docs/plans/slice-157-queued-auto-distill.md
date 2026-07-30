# Slice 157 — Queue Wiki distillation behind synchronization

## Intent

Running `awm auto-distill run` while transcript synchronization owns the
coordination lock should not force the operator to retry manually. The command
must show that it is waiting, continue automatically when synchronization
finishes, and leave the same progress trail in the Activity view when launched
by the scheduler.

## Shape

- Keep `auto-distill.lock` as a non-blocking single-distillation guard.
- Check the standing grant before waiting on synchronization.
- Wait up to ten minutes for the shared `sync.lock`.
- Report workflow stages through an optional progress callback.
- Make foreground progress describe the current workflow stage instead of
  claiming that Codex ran when the workflow only checked a lock.
- Preserve bounded failure: if synchronization exceeds the timeout, reserve no
  grant and return a distinct timeout outcome.

## Verification

- A distillation waiting behind a held sync lock resumes when that lock is
  released.
- A timed-out wait does not reserve content permission or invoke the curator.
- Another active distillation remains an immediate skip.
- CLI output contains accurate start, stage, and finish messages.
- The full AWM test, Ruff, and viewer JavaScript gates pass.
