# Slice 185: first-run README

## Intent

Make the repository installable by someone who has never seen AWM and does not
already know its Python, curator, Windows automation, or SSH assumptions.

## Documentation shape

```text
base prerequisites
  -> install AWM as an isolated uv tool
  -> choose session sources and a curator
  -> initialize the private Vault
  -> verify with doctor and runtimes
  -> enable optional Git, SSH, or scheduled distillation

contributor prerequisites
  -> uv sync --locked
  -> pytest + ruff
  -> optional Node.js syntax gate
```

## Work

1. Separate mandatory, feature-dependent, and contributor-only dependencies.
2. Provide copyable Windows PowerShell installation and verification commands.
3. Explain that uv supplies Python 3.12 and project dependencies automatically.
4. Document Codex, Claude Code, Ollama, Cursor, OpenSSH, Obsidian, and private
   Vault Git only where those integrations are used.
5. Add update, uninstall, PATH, curator, and automatic-scheduling recovery.
6. Preserve the privacy boundary between sync and model-backed distillation.

## Sources of truth

- `pyproject.toml` for Python and package dependencies.
- CLI `--help` output for commands and options.
- integration adapters for external executables and platform behavior.
- official vendor installation documentation for system tools.

## Verification

```powershell
uv run pytest
uv run ruff check src/agentworkmemory tests
node --check src/agentworkmemory/viewer/assets/app.js
```
