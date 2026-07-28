# Slice 155: Agent Work Memory rebrand

## Outcome

The fork becomes one clearly named product:

```text
Product       Agent Work Memory
Initialism    AWM
CLI           awm
Python        agentworkmemory
State root    AgentWorkMemory
Schedules     AWM Sync / AWM Auto Distill
```

AWM retains agent work sessions and promotes selected evidence into a durable
local Wiki. The name covers the complete memory lifecycle rather than only its
Wiki output.

## Scope

- Rename the active `workalmanac` Python package to `agentworkmemory`.
- Rename public Python models and workflows from `WorkAlmanac` to
  `AgentWorkMemory`.
- Replace the `wa` and `work-almanac` commands with `awm` and
  `agent-work-memory`.
- Make the distribution metadata, README, user guide, viewer, generated Wiki,
  diagnostics, errors, prompts, and tests use Agent Work Memory terminology.
- Rename Windows tasks to `AWM Sync` and `AWM Auto Distill`.
- Move the default private state root from `WorkAlmanac` to
  `AgentWorkMemory`, with an explicit one-time migration of the current user's
  state and scheduled tasks.
- Keep upstream `src/codealmanac/` as unshipped reference source so the fork
  can still compare and sync upstream code without exposing a second installed
  product.

## Architecture

This is a clean product rename, not a compatibility layer:

```python
from agentworkmemory.app import create_app
from agentworkmemory.settings import load_config

app = create_app(load_config())
```

There is one package, one command family, one state root, and one pair of task
names. The current machine migration is performed during this slice; the
shipped product does not keep `wa`, `work-almanac`, or parallel legacy state
fallbacks.

The composition root remains the only place that assembles concrete adapters,
matching the local dependency-injection guidance in
`docs/reference/cosmic-python/chapter_13_dependency_injection.md`.

## Data migration

Before reinstalling the renamed editable tool:

1. Stop foreground AWM/Agent Work Memory viewer processes.
2. Verify the source and destination state paths.
3. Move `%LOCALAPPDATA%\WorkAlmanac` to
   `%LOCALAPPDATA%\AgentWorkMemory` only when the destination does not exist.
4. Recreate the two installed schedules with the new task names and
   `agentworkmemory.scheduled` module.
5. Delete the two old task registrations only after the new tasks succeed.
6. Move the current machine's `WorkAlmanacVault` to
   `AgentWorkMemoryVault`, then update the configured path.
7. Verify the configured Vault and retained session counts through `awm doctor`.

The migration keeps all Markdown content and session identifiers unchanged.

## Package and repository surface

- Distribution: `agent-work-memory`
- Repository URL: `TaeeunKil/agent-work-memory`
- Package data belongs to `agentworkmemory`.
- Setuptools ships only `agentworkmemory*`; upstream reference packages remain
  in the checkout but not in the wheel.
- The root README documents AWM only. Historical CodeAlmanac documents remain
  under `docs/` as upstream design/reference material.

## UI

Visual thesis: a calm, local operator workspace with AWM as the unmistakable
identity and one warm activity accent.

Content plan:

1. Rail brand: `AWM / Agent Work Memory`
2. Today: retained sessions, durable Wiki pages, pending distillation
3. Sessions and Knowledge: evidence and durable memory
4. Activity: current and next scheduled operations

Interaction thesis:

- Preserve the restrained workspace entrance.
- Preserve live running-state pulse.
- Preserve row and inspector transitions as the primary affordance motion.

## Tests

- Rename the focused test suite to `test_agentworkmemory*.py`.
- Assert only `awm` and `agent-work-memory` console scripts exist.
- Assert new state, database, managed frontmatter, task, module, and branding
  names.
- Keep all behavior tests sandboxed from real user state.
- Run the complete Agent Work Memory suite, Ruff, JavaScript syntax checking,
  editable-install smoke tests, real scheduler status, and viewer QA.

## Out of scope

- Publishing the renamed distribution to PyPI.
- Deleting upstream CodeAlmanac reference source or historical plans.
- Preserving deprecated `wa` or `workalmanac` command aliases.

## Read before coding

- `MANUAL.md`
- `CLAUDE.md`
- `docs/python-port-live-agreement.md`
- `docs/reference/cosmic-python/chapter_04_service_layer.md`
- `docs/reference/cosmic-python/chapter_13_dependency_injection.md`
- `docs/agent-work-memory-user-guide.md`
- `src/agentworkmemory/app.py`
- `src/agentworkmemory/settings.py`
- `src/agentworkmemory/cli.py`
