# Work Almanac Implementation Plan

## Product goal

Work Almanac preserves one person's work with Codex, Claude, local models, and
future agent tools, then makes that work retrievable through a private Markdown
Wiki.

The first product question is not "which repository owns this transcript?" It
is:

> What agent work happened, which session did it belong to, and what should be
> retained in the personal Wiki?

## Product agreement

- One user-selected private Vault owns the Wiki.
- Repositories and paths are session context, never mandatory parents.
- Provider JSONL terminates at collector integrations.
- Imported agent records become typed session events in private local SQLite.
- Full transcript content is opt-in. Metadata collection remains useful without
  copying bodies.
- Session Markdown under `inbox/agent-sessions/` is a browseable record layer.
- Curated project, decision, problem, procedure, system, and unfinished pages
  are the durable knowledge layer.
- SQLite and FTS are local derived/runtime state and never the Wiki truth.
- `codealmanac` remains available only as an implementation donor during the
  bounded migration. New product code does not depend on old product services.

## Walking slice

```python
app = create_app(config)

receipt = app.collect.collect(
    CollectAgentRecords(provider="codex", include_content=True)
)
session = app.sessions.get(receipt.session_ids[0])
app.wiki.refresh_session(session.session_id)
results = app.search.find("decision rationale")
```

The walking slice is complete when a clean machine can:

1. initialize one Vault;
2. save a manual work note;
3. discover Codex and Claude sessions without repository registration;
4. import a provider-neutral JSON record from any other agent;
5. optionally retain normalized message/tool content;
6. regenerate a Markdown session page;
7. search both session records and Wiki Markdown;
8. repeat collection without duplicate events.

## Implementation slices

### Slice 0: product seam and local state

- [x] Add the `workalmanac` package and `wa` command.
- [x] Add platform-aware state/config paths.
- [x] Add Vault initialization and configuration.
- [x] Add an independent SQLite schema and migrations.

### Slice 1: retained agent sessions

- [x] Add provider-neutral session and event models.
- [x] Add idempotent event persistence and per-source cursors.
- [x] Add manual notes.
- [x] Add session list/show operations.

### Slice 2: transcript collectors

- [x] Port Codex discovery and normalization.
- [x] Port Claude discovery and normalization.
- [x] Add a provider-neutral JSON bundle import for local and future agents.
- [x] Skip Codex subagents and Claude subagent directories by default.
- [x] Keep cwd as context instead of filtering by a registered repository.
- [x] Require `--include-content` before transcript bodies enter local state.

### Slice 3: Wiki record projection and search

- [x] Generate stable Markdown pages under `inbox/agent-sessions/`.
- [x] Keep provider source paths out of generated frontmatter and prose.
- [x] Index session records and Wiki Markdown with SQLite FTS5.
- [x] Add `wa search` and `wa show`.

### Slice 4: verification and handoff

- [x] Unit-test storage, deduplication, discovery, normalization, and Wiki
      projection.
- [x] Exercise the CLI end to end with an isolated state directory and Vault.
- [x] Run Ruff, focused Pytest, and `git diff --check`.
- [x] Record deferred work and migration risks.

## Walking-slice commands

```powershell
wa init C:\Users\user\Documents\WorkAlmanacVault
wa collect --from codex --from claude
wa collect --from codex --from claude --include-content
wa sessions
wa search "결정 이유"
wa distill ses_... --using codex --allow-remote-content
```

`--include-content` is deliberately separate because agent transcripts may
contain source code, command output, customer data, paths, or secrets.

Any other agent can write a bundle and use `wa import bundle.json`:

```json
{
  "provider": "ollama.qwen",
  "session_id": "local-42",
  "title": "Architecture review",
  "cwd": "C:\\work\\my-project",
  "events": [
    {
      "kind": "message",
      "role": "user",
      "content": "Review the collector boundary."
    },
    {
      "kind": "message",
      "role": "assistant",
      "content": "Keep provider shapes at the edge."
    }
  ]
}
```

## Slice 5: durable Wiki distillation

Implemented in [Work Almanac Distill Slice](workalmanac-distill-plan.md):

- [x] provider-neutral curator port;
- [x] Codex and Claude Yoke curator adapters;
- [x] explicit metadata-only or selected-remote content policy;
- [x] isolated disposable curator workspace with `.git` excluded;
- [x] durable-path and Markdown validation before applying changes;
- [x] rollback for provider, validation, indexing, and session-state failures;
- [x] body-free distill receipts and session distilled state;
- [x] `wa distill` foreground CLI;
- [x] fake-curator safety tests without paid provider calls.

## Slice 6: automatic retention

Implemented in
[Work Almanac v1 Completion Plan](workalmanac-v1-completion-plan.md):

- [x] locked, idempotent `wa sync`;
- [x] body-free synchronization receipts and last-run status;
- [x] Windows Task Scheduler install, status, and removal;
- [x] explicit scheduled transcript-content opt-in;
- [x] no automatic curator or remote model calls;
- [x] scheduler command, locking, failure, and CLI contract tests.

## Slice 7: Obsidian Wiki navigation

Implemented in
[Work Almanac v1 Completion Plan](workalmanac-v1-completion-plan.md):

- [x] generated `Home.md` and durable-area indexes;
- [x] Vault-relative Obsidian Wiki links;
- [x] source-session navigation and durable-page backlinks;
- [x] deterministic rebuilds that do not rewrite unchanged files;
- [x] curator protection for managed navigation pages;
- [x] metadata-only title-leak regression coverage.

## Slice 8: local LLM curation

Implemented in
[Work Almanac v1 Completion Plan](workalmanac-v1-completion-plan.md):

- [x] loopback-only Ollama adapter and model discovery;
- [x] explicit `--allow-local-content` policy;
- [x] structured complete-file Markdown changes without model tools;
- [x] bounded existing-Wiki context and response sizes;
- [x] the same disposable workspace, validation, and rollback path;
- [x] `wa runtimes` readiness diagnostics;
- [x] mocked HTTP integration tests without a real model call.

## Validation record

- Ruff: all new Work Almanac code and changed contract tests pass.
- Walking-slice tests: 6 passed.
- Public contract and architecture tests: 78 passed, 1 pre-existing Windows
  HOME-path test deselected.
- Isolated command smoke test: `wa init`, `wa note`, and `wa search` pass.
- The legacy full suite reached 350 passed and 1 skipped before Windows-only
  launchd/POSIX-path assumptions and a later process interruption stopped the
  run. Those failures are in the legacy `codealmanac` surface and are not
  caused by the Work Almanac walking slice.

## Deliberately deferred

The daily-use v1 work continues in
[Work Almanac v1 Completion Plan](workalmanac-v1-completion-plan.md).

Post-v1 extensions remain:

- WSL/SSH transport;
- shell hooks and command/output capture;
- semantic/vector search.

These are later slices against the seams above, not prerequisites for proving
that agent records can be retained and retrieved.

## Safety invariants

- Collectors never write Wiki files.
- The Wiki writer never reads provider JSONL directly.
- No collector filters out a session merely because its cwd is unregistered.
- Content collection is explicit and visible.
- Recollection is idempotent.
- A source cursor advances only after accepted events commit.
- All generated Markdown stays under the configured Vault.
- Collectors never independently read environment variables or credential
  stores. Explicit transcript-content import may contain sensitive text already
  present in a provider transcript and is labeled accordingly.
