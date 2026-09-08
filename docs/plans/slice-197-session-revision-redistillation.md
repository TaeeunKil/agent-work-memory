# Slice 197: Re-distill updated sessions

## Goal

When a retained session receives new transcript events after a successful
distillation, automatically make it eligible for another distillation without
losing the history of the previous run.

## Shape

- Track `content_revision` and `distilled_revision` on each session.
- Increment `content_revision` only when events are appended or replaced.
- Select sessions when `distilled_at` is absent or
  `content_revision > distilled_revision`.
- Keep the first implementation full-session and idempotent; the curator reads
  existing durable pages and merges the new evidence.
- Expose the pending state consistently to the Wiki Home, diagnostics, and
  viewer instead of deriving it from `distilled_at` alone.

## Safety

- Metadata-only observations do not trigger re-distillation.
- Existing databases receive additive columns with zero defaults.
- Repeated or duplicate transcript reads do not advance the content revision.
- Rebuilds advance the revision so a changed transcript is reconsidered.

## Verification

- Test append and replace revision behavior.
- Test an already-distilled session becoming a pending candidate after new
  events.
- Run the AWM pytest, Ruff, and viewer JavaScript syntax gates.
