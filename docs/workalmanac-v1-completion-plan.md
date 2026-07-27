# Work Almanac v1 Completion Plan

## Outcome

Work Almanac v1 is a private, local-first memory system for one person's work
with Codex Desktop, Claude, and local or future agents.

The product is complete enough for daily use when the owner can install it once,
let it retain new agent sessions automatically, promote useful work into a
durable Markdown Wiki, and browse or search that Wiki in Obsidian or a local web
viewer.

## Product contract

- The user-selected Markdown Vault is the durable source of truth.
- SQLite is private local runtime state and a rebuildable search index.
- Agent session bodies are retained only after explicit opt-in.
- Remote curator runtimes receive session bodies only after explicit opt-in.
- Scheduled collection never invokes a paid or remote curator by default.
- Every provider terminates at a typed collector or curator adapter.
- The old `codealmanac` package remains a donor, never a dependency of new
  `workalmanac` product code.
- `main` remains aligned with the upstream fork; v1 develops on
  `codex/workalmanac`.

## Daily workflow

```text
Codex / Claude / another agent
            |
            v
automatic incremental collection
            |
            v
inbox/agent-sessions (private evidence)
            |
            +------ search / inspect in local viewer
            |
            v
selected remote or local curator
            |
            v
projects / decisions / problems / procedures / systems / unfinished
            |
            +------ Obsidian
            +------ local Work Almanac viewer
```

## Delivery slices

### Slice 145: automatic retention

- Add one idempotent `wa sync` operation.
- Add a single-instance lock so overlapping scheduled runs exit safely.
- Record sync receipts and expose last-run status.
- Add Windows Task Scheduler install, status, and uninstall commands.
- Default scheduled work to local content retention only; never auto-distill.

### Slice 146: Wiki navigation

- Give durable pages stable frontmatter and normalized Wiki links.
- Maintain generated home, project, decision, problem, procedure, system, and
  unfinished indexes.
- Add backlinks and source-session references without copying transcript bodies.
- Keep generated indexes deterministic and safe to rebuild.

### Slice 147: local curator

- Add an Ollama-compatible curator adapter.
- Use a strict structured file-change contract instead of shell access.
- Add runtime readiness and model discovery diagnostics.
- Preserve the same isolated Vault validation and rollback path as remote
  curators.

### Slice 148: local viewer

- Add `wa serve` for a loopback-only local application.
- Browse sessions, durable pages, backlinks, distill receipts, and sync health.
- Search both retained sessions and Wiki pages.
- Trigger explicit collection and selected distillation from the UI.
- Never serve provider transcript files or expose arbitrary filesystem paths.

### Slice 149: onboarding and migration

- Add one guided `wa setup` flow.
- Add import of existing repository `.almanac` Markdown trees into an isolated
  review namespace.
- Add configuration and installation diagnostics.
- Document Obsidian setup, backup boundaries, privacy controls, and recovery.

### Slice 150: release verification

- Exercise a clean Windows setup through collection, search, local distillation,
  viewer browsing, scheduler status, and package installation.
- Verify migration, rollback, path containment, and private-content boundaries.
- Build wheel and source distributions with all prompts and viewer assets.
- Record remaining non-v1 extensions separately.

## Explicitly later

These are useful extensions but are not required for a trustworthy personal v1:

- SSH collection from other machines;
- shell command history capture;
- semantic/vector search;
- mobile editing;
- hosted synchronization;
- fully autonomous remote distillation.

They must use the v1 collector, curator, Vault, and search seams rather than
introducing alternate storage paths.
