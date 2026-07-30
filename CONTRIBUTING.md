# Contributing to Agent Work Memory

Agent Work Memory (AWM) keeps work performed with coding agents in a private,
local record store and promotes selected conclusions into a Markdown Wiki.

## Development setup

```powershell
git clone https://github.com/TaeeunKil/agent-work-memory.git
cd agent-work-memory
uv sync --locked
uv run awm --help
```

Use `uv run awm ...` while developing from a checkout. Use an explicit
`--state-dir` for manual experiments so development never touches your real
AWM state:

```powershell
uv run awm --state-dir .tmp-state init .tmp-vault
```

## Verification

Before opening a pull request, run:

```powershell
uv run pytest
uv run ruff check src/agentworkmemory tests/test_agentworkmemory*.py
node --check src/agentworkmemory/viewer/assets/app.js
git diff --check
```

Tests must use temporary state and Vault paths. Do not commit transcripts,
private Wiki content, credentials, SSH configuration, or generated state.

## Architecture

- `src/agentworkmemory/services/` owns domain behavior and ports.
- `src/agentworkmemory/integrations/` owns operating-system and provider
  adapters.
- `src/agentworkmemory/workflows/` coordinates application use cases.
- `src/agentworkmemory/app.py` is the composition root.
- `src/codealmanac/` is retained only as unshipped upstream reference source.

Read `CLAUDE.md`, `MANUAL.md`, and the current slice plan before changing code.
User-facing work should update the README or the AWM user guide in the same
change.
