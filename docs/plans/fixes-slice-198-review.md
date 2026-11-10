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
