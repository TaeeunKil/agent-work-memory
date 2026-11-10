# Slice 198 review and recovery

Reviewed against CLAUDE.md and .claude/agents/review.md with a separate read-only
reviewer. No real user state was used by tests or the reviewer.

## Findings fixed

- A shared provider ID was also a shared cursor key. Recovering a retained row
  could therefore skip its baseline events. Cursors now follow the canonical
  AWM session ID, including same-record archive moves. Old unowned cursors are
  not reused: the next collection replays a retained session once. Repeated
  subsequent reads are incremental.
- A path-derived session ID could already belong to a record relocated to a
  different live path. Exact path lookup now precedes relocation; a reappearing
  path receives a new ID if the original is occupied. Both records are retained.
- Added regression cases for both findings, observed failures, then passed them
  with the fixes. Concurrent capture during review, untouched Windows handoff,
  inherited desktop Core routing, and expired grant status also have regression
  coverage.

## Implementation decisions

- Retain the full-session merge behavior from slice 197.
- Keep Windows sandbox and network restrictions unchanged. Only app-specific
  Core routing environment variables are removed in the standalone CLI child.
- An explicit empty handoff is a valid no-op; an untouched placeholder is failure.
- Existing systemd files had line-length lint failures; formatting only was
  corrected to make the required AWM lint gate pass.
- The installed editable checkout is used for recovery after an SQLite backup.
  This is an operational run authorized by the user, not an automated test.

## Verification record

Final project suite: 223 passed (`uv run pytest -q`). AWM Ruff and viewer
JavaScript syntax checks passed. One intermediate Windows asyncio readiness
test hit a transient socket setup error; it passed in isolation and the final
full suite passed.

Live recovery was started separately after a consistent SQLite backup. Its
completion and publication receipts are operational state, not public test
fixtures.

## Live concurrency follow-up

The first live manual review reached the curator successfully, but overlapped
the sync search rebuild and failed with a SQLite write lock. The manual CLI
had bypassed the coordination already used by automatic and viewer reviews.
It now acquires the distillation lock, waits for synchronization, and holds the
sync lock through selection and completion. Two regressions failed before the
fix and passed afterward. The full suite passed with 225 tests. A separate
read-only review of this follow-up reported no findings.

Live sync subsequently completed successfully: 457 sessions and 113,276 events
processed (including one-time cursor migration replay). A serialized manual
retry was observed waiting for sync and starting only after its completion.

## Multiple rollout files

Real-file reconciliation also showed that distinct Codex rollouts can retain
the same metadata session ID. Discovery now distinguishes rollout filenames,
while still preferring the live copy of the same file over its archive copy.
Missing-path relocation uses an unambiguous matching filename before the
single-missing-record fallback. This preserves IDs and cursors when several
same-provider-ID files move to the archive together. Both discovery and the
multi-file archive interaction have regression tests observed failing first.

Final verification after rollout/archive fixes: 227 tests passed; Ruff and
viewer JavaScript syntax checks passed.
