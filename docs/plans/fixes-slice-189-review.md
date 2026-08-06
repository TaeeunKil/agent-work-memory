# Slice 189 review fixes

## Review scope

Reviewed the complete Codex discovery, transcript normalization, cursor replay,
session identity, Vault projection, and Git publication flow against
`CLAUDE.md` and `.claude/agents/review.md`. The review included the changed
tests and all callers of the new replay and record-rendering boundaries.

## Findings resolved

### Incremental duplicate messages could cross a cursor boundary

A canonical `response_item` could be collected in one sync and its duplicate
`event_msg` representation in the next. The second read had no canonical item
available for comparison. Codex incremental reads now retain eight prior lines
as normalization context and return only events newer than the cursor. A
regression test covers the split-read case.

### Rendered part metadata could exceed the nominal byte budget

Event bodies were grouped below the target, but an unexpectedly large title or
frontmatter block could push the final file over it. Final rendered parts are
now checked against the actual UTF-8 byte budget before any Vault replacement.

### Append and replay duplicated cursor-finalization SQL

Both database paths must update the same cursor version, physical source path,
and captured-content state. That shared transaction tail now lives in one
`finish_capture` helper so schema changes cannot drift between append and
replacement behavior.

### Zero-event replays were not counted as session updates

A normalizer migration can legitimately remove every retained event from a
telemetry-only session. The collection receipt now counts that replacement as
an updated session even though `events_added` remains zero.

## Final assessment

No findings remain. The provider-specific normalization stays in the transcript
integration, the workflow owns replay selection, SQLite owns atomic projection
replacement, Vault rendering owns deterministic parts, and Git publication owns
the final file-size refusal.

Residual risk is limited to applying the migration to an actively used local
database and Vault. That destructive-in-place step was deliberately not run
from the isolated feature worktree. The exact 621,776,873-byte archived Codex
source was instead replayed read-only: it produced 15,987 typed events, zero raw
transport envelopes, and three Markdown parts below 16 MiB each.
