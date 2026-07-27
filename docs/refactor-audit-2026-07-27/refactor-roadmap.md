# Refactor Roadmap

## MVP definition

The first useful version runs on one Windows machine, recognizes Windows and
WSL origins, collects Codex and Claude sessions plus manual notes, lets the
user correct session grouping, distills selected sessions into one private
Markdown vault, and supports lexical search and show.

It does not yet:

- capture arbitrary shell history;
- install on SSH servers;
- synchronize multiple nodes;
- use a local model as curator;
- provide semantic search;
- ship telemetry or auto-update;
- run unattended background workers;
- preserve the CodeAlmanac CLI contract.

## Phase 0: Freeze and name the product fork

### Goal

Stop new work from reinforcing the repository-wiki center.

### Changes

- Choose the final product/package/CLI name; use `WorkAlmanac` and `wa` as the
  working names.
- Write a breaking product agreement that supersedes CodeAlmanac's
  repository-owned constraints.
- Freeze auto-update, telemetry, hosted aspirations, topic-editing breadth, and
  public packaging work.
- Record a behavior inventory for reusable search, page parsing, jobs, viewer,
  source adapters, and harness adapters.

### Why first

Renaming is architecture. Carrying `repository`, `codealmanac`, `build`, and the
current meaning of `sync` into new code will preserve the wrong decisions.

### Risk

An overly broad mechanical rename can hide which parts are truly reusable.

### Verification

- New product agreement has no compatibility mode.
- Target nouns appear in plans before production edits begin.

## Phase 1: Establish one vault without AI

### Goal

Make the person-owned Markdown vault the only durable knowledge root.

### Changes

- Introduce `Vault`, vault registration/selection, and one fixed vault root.
- Adapt page parsing, source citations, FTS, search, show, and validate to vault
  scope.
- Add the Work Almanac folder/manual templates.
- Remove repository ownership from read paths; keep repositories only as
  project/source context.

### Why first

Every later capture or curator feature needs a correct mutation and reading
boundary.

### Risk

Trying to support per-repository CodeAlmanac and one-vault Work Almanac
simultaneously.

### Verification

- A hand-written vault validates and indexes.
- Search/show work without a registered code repository.
- No production Markdown write escapes the vault root.

## Phase 2: Add the capture ledger and manual notes

### Goal

Prove event identity, cursors, privacy, retention, and session grouping without
provider complexity.

### Changes

- Add typed `Host`, `Environment`, `Workspace`, `CaptureSource`,
  `CaptureEvent`, `CaptureCursor`, and `WorkSession` models.
- Add dedicated ledger tables and idempotent append behavior.
- Add privacy allowlists, protected-content references, retention, and
  payload-size limits.
- Implement `wa note`, `wa inbox`, deterministic grouping, and explicit
  session merge/split/assign/close.

### Why first

Manual notes are a complete input source with minimal external-format risk.
They test the new data model before transcript adapters distort it.

### Risk

Letting arbitrary provider payload dictionaries leak into the core model.

### Verification

- Re-importing the same note/batch creates no duplicate event.
- Sensitive test fixtures are redacted before persistence.
- Purging selected raw content leaves the accepted session record intact.
- Cursor advancement is transactional with accepted events.
- Ledger and Markdown use separate stores and retention rules.

## Phase 3: Port Codex and Claude as collectors

### Goal

Turn the existing transcript readers into provider-neutral capture adapters.

### Changes

- Reuse Codex/Claude discovery and typed JSONL parsing.
- Emit structured events instead of one rendered transcript blob.
- Preserve stable provider session/event/tool ids when present.
- Treat cwd/repository as hints; add Windows/WSL path aliases and nested project
  matching.
- Track one cursor per transcript/source stream.

### Why now

The core capture contract has already been proven by manual notes.

### Risk

Persisting too much raw transcript content or reintroducing exact-root
repository ownership.

### Verification

- Golden transcript fixtures for both providers produce equivalent semantic
  event kinds.
- Appending transcript lines imports only the new suffix.
- Truncation is explicit at the curator read boundary, not at event identity.
- A session outside a Git repository is still captured.

## Phase 4: Replace ingest/build with distill

### Goal

Use a selected curator agent to promote ready sessions into durable memory.

### Changes

- Replace repository build/ingest prompt payloads with a vault/session payload.
- Add Work Almanac writing manuals for daily, project, decision, problem,
  procedure, system, and unfinished pages.
- Reuse normalized harness events, validation, change tracking, and optional
  Git source-control policy.
- Start with explicit foreground execution and a content-access manifest.
- Preserve direct writer ownership: no proposal/apply state machine.

### Why now

The curator consumes a stable evidence model instead of provider-specific raw
text.

### Risk

Generating daily summaries while failing to update long-lived project,
decision, and problem pages.

### Verification

- A mixed Codex/Claude session creates or updates the correct durable pages.
- Re-distilling the same session is idempotent or produces no-op.
- The curator cannot write outside the vault.
- Page citations resolve to real session/event evidence.
- A receipt shows which evidence was exposed to which runtime.

## Phase 5: Rebuild the viewer and job observability

### Goal

Make personal work and long curator runs understandable without exposing raw
evidence.

### Changes

- Rebuild the viewer around recent sessions, projects, decisions, problems,
  procedures, systems, unfinished work, and evidence navigation.
- Keep raw content hidden by default.
- Restore a vault-scoped run ledger, detached workers, cancellation, and
  attachable logs only where foreground distill runs prove too long.
- Keep work sessions and curator jobs as separate services and UI concepts.

### Why now

The viewer now has stable session and knowledge models to present. The job
system returns in response to measured execution needs, not as inherited
product structure.

### Risk

Turning the product into an activity-surveillance dashboard or a jobs console.

### Verification

- The five core questions are answerable without opening SQLite or provider
  transcript files.
- Session results and durable knowledge are visibly distinct.
- Raw content is absent unless explicitly requested.
- Cancelled/failed curator work cannot leave a trusted partial result.

## Phase 6: Import existing CodeAlmanac knowledge

### Goal

Preserve useful existing pages without keeping per-repository wikis as a
second source of truth.

### Changes

- Add a one-shot importer into `projects/` or another durable neighborhood.
- Assign stable memory ids and translate useful evidence references.
- Report copied, skipped, and manually placeable pages.
- Preserve historical behavior in the fork's Git history, not in the new
  runtime.

### Verification

- Imported pages are searchable from the personal vault.
- The new runtime has no dependency on the old repository registry.

## Phase 7: Add one-writer multi-host transport

### Goal

Collect from Windows, WSL, and SSH Linux nodes into one canonical vault.

### Changes

- Give every node a stable identity and local outgoing spool.
- Define authenticated, checksummed, idempotent capture batches.
- Start with filesystem bundles for Windows/WSL and SSH pull for remote Linux.
- Keep the canonical ledger and curator on one vault host.
- Let other machines mirror Markdown through Git for reading if desired.

### Why later

Transport should carry a proven capture contract. It should not define it.

### Verification

- Replayed batches are harmless and interrupted transfers resume safely.
- A collector cannot edit Markdown or read unrelated ledger content.
- Content-class policy is enforced across transport.
- Host clocks do not determine event identity.

## Phase 8: Add opt-in shell evidence and automation

### Goal

Capture missing evidence and run trusted workflows unattended.

### Changes

- Add Git commit/branch/diff-summary events.
- Add an explicit `wa run -- <command>` or shell-session integration after its
  UX is agreed.
- Record SSH work through an explicit wrapper or remote collector, not by
  scraping all command history.
- Select scheduler adapters by platform in the composition root.
- Implement Windows Task Scheduler first, then systemd/launchd only when used.
- Run frequent deterministic collect and less frequent distill/garden tasks.
- Unattended remote-model content access requires an explicit standing grant.

### Why later

Shell capture has the highest secret and surveillance risk.

### Risk

Recording command arguments, environment values, tokens, or private paths.

### Verification

- Secret-bearing fixtures never reach the ledger.
- Exit status and bounded summaries survive without raw output by default.
- Users can see exactly which collectors are enabled.
- Offline/restart/retry causes no skipped or duplicated events.

## Phase 9: Evaluate a local curator

### Goal

Add one concrete local-model agent runner only if it can safely maintain the
vault.

### Changes

- Choose an actual tool-capable local runner and model.
- Implement the existing curator port, not a generic provider plugin system.
- Benchmark page selection, citation grounding, no-op judgment, and bounded
  file writes against Codex/Claude runs.

### Verification

- The local curator passes the same behavioral suite and mutation-safety gates.
- Quality is acceptable on representative personal sessions.
- Failure falls back to a failed job, never a partially trusted silent success.
