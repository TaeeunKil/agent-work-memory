# Slice 165 — Non-empty distillation queue

## Intent

Do not spend curator runtime or standing-grant reservations on transcript
session shells that contain no captured events.

## Shape

The sessions store returns the set of session IDs backed by at least one
`agent_events` row using an indexed `EXISTS` query. The shared
`distillation_candidates()` policy requires membership in that set before
applying the existing content-captured, pending, and internal-workspace rules.

Because CLI pending distillation, scheduled auto-distill, and viewer Wiki builds
all use this service policy, the filter applies consistently to every batch
entry point.

## Invariants

- A session with `content_captured=true` but zero events is not pending.
- A non-empty session in the same workspace remains eligible.
- Explicit session-ID distillation remains available for operator diagnostics.
- No provider-specific Cursor rule is introduced.

## Verification

- Service test covers an empty captured shell beside a real manual session.
- Full pytest, Ruff, and viewer JavaScript gates.
- Inspect the next real auto-distill selection before consuming the remaining
  standing grant.
