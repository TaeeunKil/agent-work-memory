# Source Map

## Current product flow

```text
Codex/Claude transcript files
        |
        v
TranscriptDiscoveryAdapter
        |
        v
SyncEvaluator -- exact transcript.cwd == registered repository root
        |
        v
one ingest run per repository
        |
        v
SourceRuntime -- prompt-facing rendered text, capped at 60,000 characters
        |
        v
Codex/Claude writer edits repository/almanac/
        |
        v
Git history + derived per-repository FTS index
```

This is coherent for a codebase wiki. It is not a neutral work-memory pipeline.
The repository is the selection key, run owner, working directory, mutation
boundary, page root, and index scope.

## Boundary judgments

| Current boundary | Evidence | Judgment | Work Almanac movement |
|---|---|---|---|
| Explicit composition root | `src/codealmanac/app.py` | Keep | Rename and rewire around vault, capture ledger, sessions, curator, and index. |
| Services, workflows, ports, integrations | `src/codealmanac/services/`, `workflows/`, `integrations/` | Keep | The dependency direction is sound. Change product nouns, not the overall layering. |
| Repository registry | `services/repositories/models.py`, `service.py` | Redesign | A single personal vault is the durable knowledge root. Repositories become optional project evidence/context, not storage owners. |
| Source address/runtime adapters | `services/sources/`, `integrations/sources/` | Keep and split | Preserve typed source adapters, but separate continuous collectors from explicit ingest material. |
| Transcript discovery | `integrations/sources/transcripts/codex.py`, `claude.py` | Keep as adapters | Project into provider-neutral capture events before prompt rendering. Add provider metadata, host, environment, cursor, and privacy classification. |
| Transcript normalization | `transcripts/entries.py`, `rendering.py` | Redesign | It currently turns provider records into lossy prompt text. Normalize into structured events first; render only at the curator boundary. |
| Sync policy | `workflows/sync/evaluation.py`, `queue.py` | Delete/replace | Exact-root repository matching and one global modified-time watermark do not support nested cwd, non-repo work, multiple hosts, or reliable replay. `sync` should eventually mean node transport, not transcript scanning. |
| Build/Ingest/Garden lifecycle | `workflows/build/`, `ingest/`, `garden/` | Rename and reshape | `collect` is deterministic intake, `distill` is AI knowledge promotion, and `garden` remains knowledge maintenance. First-vault creation is deterministic; no full codebase build is required. |
| Durable run/job ledger | `services/runs/`, `workflows/run_queue/` | Keep | It is useful for distill/garden observability and cancellation. Remove the mandatory `repository_id`; runs target a vault and optional project/session set. |
| Harness abstraction | `services/harnesses/`, `integrations/harnesses/yoke/` | Keep, generalize later | Input source and curator provider are already separate axes. Do not add a plugin system; add another adapter only when a concrete local-model runner is selected. |
| Markdown page model | `services/wiki/`, `manual/` | Keep and generalize | Retain readable Markdown, links, topics, and citations. Replace code-only authority assumptions and file-centric evidence with session/event/source references. |
| Derived FTS index | `services/index/` | Keep | Continue treating SQLite FTS as rebuildable read state for durable pages. Give the capture ledger its own schema and retention policy. |
| Viewer | `services/viewer/`, `server/` | Keep, change information architecture | Add Today, Inbox, Sessions, Projects, Decisions, Problems, Procedures, Systems, and Unfinished views. Do not make the viewer a raw surveillance dashboard by default. |
| Scheduler port | `services/automation/ports.py` | Keep | Replace unconditional `LaunchdSchedulerAdapter` wiring in `app.py` with platform selection. Implement Windows Task Scheduler first for the current host, then systemd for a Linux hub. |
| Auto-update and telemetry | `services/updates/`, `services/telemetry/` | Freeze/delete candidate | They are unrelated to proving the personal-memory loop and expand privacy/release surface. Reconsider only after the fork has an install/distribution plan. |

## Product assumptions that must be broken

1. A work session belongs to exactly one registered repository.
2. A repository root is the only safe working directory for AI work.
3. Transcript modification time is an adequate intake cursor.
4. Recently modified transcripts can be marked processed when work is merely
   queued.
5. Durable Markdown is the first representation of captured activity.
6. Code files, commits, and PRs dominate evidence.
7. macOS launchd is always available.
8. Codex and Claude are the complete provider catalog.

## Legitimate complexity worth preserving

- typed external normalization at adapter edges;
- explicit run states, events, cancellation, and worker locks;
- direct agent writing with validation instead of proposal/apply state machines;
- Markdown as durable knowledge and SQLite as derived query state;
- source citations and backlinks;
- prompt-owned judgment about what deserves durable memory;
- local-first operation and a read-only viewer.
