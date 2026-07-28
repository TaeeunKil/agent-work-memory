# Slice 157 review fixes

## Finding

The initial implementation reused one `skipped-locked` result for both an
active distillation and an expired synchronization wait. That forced the CLI
to print an ambiguous combined explanation even though the workflow knew the
exact cause.

## Fix

- Replace the shared result with `distillation-running` and
  `sync-wait-expired`.
- Map each typed outcome to one precise operator-facing message.
- Keep progress callbacks responsible for the live stage trail and receipts
  responsible for the final outcome.

No additional architectural findings remained after the fix.
