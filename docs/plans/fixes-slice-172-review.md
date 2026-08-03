# Slice 172 review fixes

## Review

Two findings were fixed:

- Keep the current Cursor Agent JSONL schema and parsing machinery in
  `cursor_agent.py` instead of growing the legacy SQLite integration into one
  large module with two reasons to change.
- Exercise the catalog/content-path seam through the complete collection
  workflow, not discovery alone, so a header-backed JSONL transcript proves it
  can retain events under the established session identity.

No further findings.

## Residual risk

Cursor controls these local formats and may evolve them again. Unknown JSONL
records and content parts are ignored at the provider boundary, and the
legacy SQLite reader remains available. Cursor Background Agent conversations
stored only in Cursor's remote service are outside this local collector.

## Validation

- `uv run pytest tests`
- `uv run ruff check src/agentworkmemory tests`
- `node --check src/agentworkmemory/viewer/assets/app.js`
- Read-only discovery against the current local Cursor SQLite and JSONL stores
- Foreground `awm sync --from cursor --include-content`
