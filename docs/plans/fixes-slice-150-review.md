# Fixes: Slice 150 release-verification review

Status: complete.

## Must-fix finding

`wa doctor --runtimes` can crash when a Yoke provider readiness probe raises an
operating-system error such as Windows `PermissionError`. The adapter currently
normalizes a few concrete external failures but not their shared `OSError`
boundary.

The Yoke curator adapter must:

- normalize all expected filesystem/process startup failures into an
  unavailable readiness result;
- return a failed curator result if the same class of external failure occurs
  during a run;
- expose only the exception type and a bounded repair hint, never the raw
  exception text or a local executable path.

## Must-fix finding: search must not rebuild a current index on every query

The first real Vault retained 148,576 events. `wa search` then exceeded one
minute because `SearchService.find()` rebuilt the complete FTS index even
though setup had just refreshed it.

Persist a cheap typed source signature beside the FTS table. Search should
rebuild only when session/event revisions or Markdown file metadata differ
from the indexed signature. Collection, migration, and distillation can still
refresh explicitly at their existing write boundaries.

## Scope

- Broaden the existing Yoke adapter error boundary to `OSError`.
- Redact external exception messages at readiness and run boundaries.
- Add regression coverage for a Windows-style permission failure.
- Add source-signature tracking and regression coverage for fresh/stale search.
- Reinstall the editable tool and rerun real `wa doctor --runtimes`.
- Verify a real no-match search completes without exposing record content.

## Out of scope

- Changing Yoke itself.
- Elevating runtime subprocess permissions.
- Automatically signing in Codex or Claude.

## Read before coding

- `CLAUDE.md`
- `MANUAL.md`
- `.claude/agents/review.md`
- `src/workalmanac/integrations/curators/yoke.py`

## Verification

- Focused Yoke curator test.
- Complete Work Almanac regression suite.
- Ruff format and lint.
- Real installed-tool diagnostics.
