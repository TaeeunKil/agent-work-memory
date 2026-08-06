# Slice 187 review fixes

## Review result

The model and reasoning-effort path is additive and keeps provider-specific
translation at the Yoke boundary. Existing automatic grants are preserved by
`AutoDistillationService.configure`; no scheduler task or reservation counter
is replaced. The CLI reports the active curator selection before a direct or
scheduled run can send selected content.

## Verification

- `uv run pytest -q` — 154 passed.
- `uv run ruff check src/agentworkmemory tests/test_agentworkmemory_distill.py tests/test_agentworkmemory_auto_distill.py` — passed.
- `node --check src/agentworkmemory/viewer/assets/app.js` — passed.
- `git diff --check` — passed.
