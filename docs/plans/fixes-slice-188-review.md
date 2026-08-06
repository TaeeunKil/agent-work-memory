# Slice 188 review fixes

## Review result

The backlog grant resize preserves the scheduler, expiry, content-access
scope, and reservation count. Review found one additional failure boundary:
Codex can emit malformed YAML frontmatter while rewriting an existing page.
The curator workspace now restores the baseline metadata and keeps the
curator body when the current frontmatter cannot be parsed, allowing strict
validation to continue without weakening validation for new pages.

## Verification

- Malformed existing frontmatter is repaired from the baseline and validated.
- `uv run pytest -q` and the standard AWM gates remain required before commit.
