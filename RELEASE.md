# Releasing Agent Work Memory

AWM is currently installed from a checkout or Git repository. Publishing the
distribution to PyPI remains disabled until package ownership and credentials
are explicitly decided.

## Build and verify

```powershell
uv sync --locked
uv run pytest
uv run ruff check src/agentworkmemory tests/test_agentworkmemory*.py
node --check src/agentworkmemory/viewer/assets/app.js
uv build --out-dir dist
uvx twine check dist/*
```

Verify that the wheel contains `agentworkmemory/` and exposes only these console
scripts:

```text
awm
agent-work-memory
```

Smoke-test the built artifact in a clean environment with an isolated state
directory and Vault. Never use a release smoke test against real user state.

## Install from Git

```powershell
uv tool install git+https://github.com/TaeeunKil/agent-work-memory.git
awm --help
awm doctor
```

For editable local development:

```powershell
uv tool install --editable . --force
```

## Release checklist

1. Update the version in `pyproject.toml` and regenerate `uv.lock`.
2. Add the user-visible changes to `CHANGELOG.md`.
3. Run the complete verification block above.
4. Confirm the viewer opens and Activity reports current and next scheduled
   AWM operations.
5. Tag only the reviewed commit.

Do not enable `.github/workflows/publish.yml` until the publishing policy,
provenance, and credential owner are documented.
