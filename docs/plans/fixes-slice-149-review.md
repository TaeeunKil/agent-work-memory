# Fixes: Slice 149 review

## Review findings

### Must-fix: validate a legacy import before the first Vault write

`ImportLegacyAlmanacWorkflow` currently validates encoding and the 50 MB
boundary while it copies. A bad later file can therefore leave an incomplete
namespace even though the command reports failure.

Reshape the workflow into two explicit phases:

1. discover and validate the complete bounded Markdown bundle;
2. copy the already-validated bundle into the isolated Vault namespace.

The source remains untouched, retries remain idempotent, and invalid bundles
leave the target namespace empty.

### Should-fix: make the namespace identity stable on Windows

Windows paths are case-insensitive, but hashing the raw resolved path can assign
two namespaces to two spellings of the same repository. Normalize the path with
the platform path rules before hashing it.

## Scope

- Refactor the legacy import workflow around a typed validated page bundle.
- Add regression coverage for invalid later content causing no partial writes.
- Add platform-aware namespace identity coverage.

## Out of scope

- Mirroring deletions from the source into a prior import.
- Importing non-Markdown assets.
- Merging imported pages into curator-writable durable areas.

## Read before coding

- `CLAUDE.md`
- `MANUAL.md`
- `docs/workalmanac-v1-completion-plan.md`
- `src/workalmanac/workflows/import_legacy/`

## Verification

- Focused legacy-import tests.
- Work Almanac regression suite.
- Ruff format and lint.
- `git diff --check`.
