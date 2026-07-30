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

Status: complete on `codex/workalmanac`.

- [x] Add one idempotent `wa sync` operation.
- [x] Add a single-instance lock so overlapping scheduled runs exit safely.
- [x] Record sync receipts and expose last-run status.
- [x] Add Windows Task Scheduler install, status, and uninstall commands.
- [x] Keep content retention opt-in and never auto-distill.

Daily commands:

```powershell
wa sync --from codex --from claude --include-content
wa auto install --every 5 --from codex --from claude --include-content
wa auto status
wa auto remove
```

Automatic collection stores local evidence and refreshes search. It never starts
a curator, sends transcript bodies to a model, or incurs model usage.

### Slice 146: Wiki navigation

Status: complete on `codex/workalmanac`.

- [x] Parse durable-page frontmatter and normalized Obsidian Wiki links.
- [x] Maintain generated home, project, decision, problem, procedure, system,
  and unfinished indexes.
- [x] Add backlinks and source-session references without copying transcript
  bodies.
- [x] Keep generated indexes deterministic and safe to rebuild.
- [x] Reserve `Home.md` and `_index.md` from curator writes.
- [x] Withhold title-derived content from metadata-only curator prompts.

### Slice 147: local curator

Status: complete on `codex/workalmanac`.

- [x] Add an Ollama-compatible loopback curator adapter.
- [x] Use a strict structured file-change contract instead of filesystem or
  shell tools.
- [x] Add runtime readiness and model discovery diagnostics.
- [x] Preserve the same isolated Vault validation and rollback path as remote
  curators.
- [x] Bound existing-Wiki context, response size, file count, and file size.
- [x] Reject remote endpoints, remote-content policy, path escapes, and managed
  page writes.

Local usage:

```powershell
wa runtimes
wa distill ses_... --using ollama --model qwen3:8b --allow-local-content
```

For a non-default local port, place the global option before the command:

```powershell
wa --ollama-url http://127.0.0.1:11435 runtimes
```

The adapter uses Ollama's local `/api/tags` and `/api/chat` endpoints with a
JSON Schema response, non-streaming output, and temperature zero. It never gives
the model shell or direct filesystem access.

### Slice 148: local viewer

Status: complete on `codex/workalmanac`.

- [x] Add `wa serve` for a loopback-only local application.
- [x] Browse sessions, durable pages, backlinks, distill receipts, and sync
  health.
- [x] Search retained sessions and durable Wiki pages without generated-page
  duplicates.
- [x] Trigger explicit collection and selected distillation from the UI.
- [x] Never serve provider transcript files or expose arbitrary filesystem
  paths.
- [x] Require a custom same-origin action header for JSON mutations.
- [x] Disable raw Markdown HTML and send no-store, CSP, frame, referrer, and
  content-type security headers.
- [x] Ship responsive packaged HTML, CSS, and JavaScript with no remote assets.

Run:

```powershell
wa serve
wa serve --port 4932 --no-open
```

The server always binds to `127.0.0.1`. There is no option to expose it on a
LAN interface.

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
