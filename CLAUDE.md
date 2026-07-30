> **COMPULSORY:** read [`MANUAL.md`](MANUAL.md) before implementing a feature.

# Agent Work Memory development agreement

Agent Work Memory (AWM) is a private, person-owned memory and Wiki for work
performed with Codex, Claude, local LLMs, and provider-neutral agent records.

The active product lives under `src/agentworkmemory/`. The upstream
`src/codealmanac/` tree is unshipped reference source; do not add new AWM
features there.

## Product contract

- Product name: **Agent Work Memory**
- Initialism and CLI: **AWM** / `awm`
- Python package: `agentworkmemory`
- Default state root: `AgentWorkMemory`
- Windows tasks: `AWM Sync` and `AWM Auto Distill`
- Durable knowledge: ordinary Markdown in the user-selected private Vault
- Evidence: retained local sessions and events in private SQLite state
- Automatic sync never invokes a curator
- Distillation requires explicit local- or remote-content permission
- Viewer binds to loopback only

There is one canonical product name. Do not add deprecated command aliases,
legacy package names, or parallel state paths.

## Architecture

- `app.py` is the composition root.
- Services own product verbs and typed models.
- Stores own persistence behavior.
- Integrations implement service-owned ports.
- Workflows coordinate services; the CLI and viewer are adapters.
- Provider-specific behavior stays at provider boundaries.
- Runtime state never belongs in the Markdown Vault.

Use Pydantic models for shaped data, enums for finite choices, and static
attribute access. Avoid loose structured dictionaries, compatibility husks,
provider conditionals outside integrations, and orchestration that duplicates
agent judgment.

## Working method

Work slice by slice:

1. Write `docs/plans/slice-N-*.md`.
2. Reshape the architecture if the feature does not fit cleanly.
3. Implement and test the slice.
4. Review using `.claude/agents/review.md`.
5. Record review fixes in `docs/plans/fixes-slice-N-review.md`.
6. Commit buildable work using the repository conventions.

Default gates for AWM changes:

```powershell
uv run pytest tests/test_agentworkmemory*.py
uv run ruff check src/agentworkmemory tests/test_agentworkmemory*.py
node --check src/agentworkmemory/viewer/assets/app.js
```

Tests touching user state must use isolated paths and never read or mutate the
real AWM state, Vault, SSH configuration, or Windows tasks.

## Naming

Use `AgentWorkMemory` only where a public Python type represents the assembled
product or its configuration. Prefer direct domain nouns elsewhere:
`Session`, `ActivityRun`, `ViewerSchedule`, `VaultService`, and
`DistillSessionsWorkflow`.

The Wiki is a durable output of AWM, not the whole product. User-facing copy
should say “memory” for the complete system and “Wiki” for promoted Markdown.

## UI

The viewer is a restrained local operations workspace:

- AWM is the strongest identity.
- Today, Sessions, Knowledge, and Activity are the primary surfaces.
- Prefer plain layout, dividers, typography, and whitespace over cards.
- Use the warm accent only for actions and live state.
- Utility copy should explain status, scope, freshness, or action.

## Upstream reference

Historical CodeAlmanac plans and `src/codealmanac/` may be consulted for
architecture and behavior. They are not product truth when they conflict with
this agreement, current AWM code, or the current slice plan.
