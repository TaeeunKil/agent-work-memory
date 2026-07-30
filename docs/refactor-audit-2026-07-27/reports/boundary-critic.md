# Boundary critic: from CodeAlmanac to a personal Work Almanac

## Audit goal

Critically audit the composition root, repository registry, transcript discovery, source adapters, sync, run queue, workflows, wiki, and index to determine which boundaries can support a local-first personal Work Almanac spanning Codex, Claude, local LLMs, Windows, WSL, Linux, and SSH.

Core questions:

- Which boundaries express durable product concepts?
- Which boundaries only look general because the current product has one dominant assumption?
- Can a second execution environment, agent provider, or non-repository work context be added without teardown?
- What should be kept, simplified, deleted, or redesigned before implementation?

Non-goals:

- Do not modify production code.
- Do not design a hosted service.
- Do not preserve repository-local behavior merely because the current code has tests for it.

## Executive verdict

The current code has several good implementation seams, but the central domain boundary is wrong for a personal Work Almanac.

Today the system equates:

```text
Repository
  = registered unit
  = source-code root
  = exact transcript cwd
  = wiki storage location
  = run ownership
  = index partition
  = git commit boundary
```

That equation is explicit in `Repository`, `SyncEvaluator`, `RunRecord`, `OperationRunner`, and `IndexService`. It works for "one wiki inside each code repository." It does not work for "remember my work regardless of which agent, OS, machine, or transport produced it."

The target product needs four independent axes:

```text
Vault       where durable personal knowledge lives
Scope       what project/client/topic the work belongs to
Location    where the source was observed (node + OS + path + transport)
Source      which provider/session/artifact produced the evidence
```

Do not add Windows paths, WSL translations, SSH hosts, or local-LLM enum cases to `Repository`. That would preserve the wrong center and spread more special cases. First replace the repository-owned topology with a vault/scope/location/source model.

The best reusable assets are:

- explicit composition in `app.py`
- service-owned ports with integration adapters
- provider-specific transcript discovery modules
- typed normalized events
- Markdown as canonical, inspectable knowledge
- source citations and ordinary Markdown links
- a derived SQLite FTS5 index
- a durable run/event ledger for autonomous work
- architecture tests that enforce dependency direction

The most contaminated or misleading assets are:

- `RepositoriesService` as the universal context selector
- exact `transcript.cwd == repository.root_path` sync routing
- one global timestamp as the only sync cursor
- fixed `CodeAlmanac/RunKind/HarnessKind/TranscriptApp` enums
- `OperationRunner`, which always assumes a repository-mutating wiki job
- `BuildWorkflow` and `GardenWorkflow` as top-level product verbs
- per-repository `almanac/` initialization and per-repository index databases
- git auto-commit policy baked into every lifecycle workflow
- launchd as the unconditional default scheduler

## Current boundary map

```text
CLI / server
    |
    v
app.create_app()
    |
    +-- RepositoriesService --> RepositoryStore --> ~/.codealmanac/codealmanac.db
    +-- WikiService ---------> <repo>/almanac/
    +-- IndexService --------> ~/.codealmanac/repos/<repo-id>/index.db
    +-- SourcesService ------> Claude/Codex discovery + source runtime adapters
    +-- RunsService ---------> RunStore --> global SQLite
    +-- HarnessesService ----> Yoke --> Codex or Claude
    |
    +-- BuildWorkflow
    +-- IngestWorkflow ------> source snapshots --> agent mutates <repo>/almanac/
    +-- GardenWorkflow ------> agent repairs <repo>/almanac/
    +-- RunQueue ------------> detached worker/executor processes
    `-- SyncWorkflow --------> discover transcripts
                               group by exact registered cwd
                               queue one ingest per repository
```

This is internally coherent. The problem is not that the code lacks layers. The problem is that nearly every layer preserves the same narrow product assumption.

## Boundary judgment summary

| Boundary | Judgment | Reason |
|---|---|---|
| `app.py` composition root | **Keep, simplify** | Explicit wiring and replaceable adapters are real seams; the aggregate duplicates service lists and hard-codes platform defaults. |
| Repository registry | **Redesign** | A local filesystem code root is not a personal-work identity, remote identity, or vault identity. |
| Transcript discovery ports | **Keep** | Provider discovery is a genuine variable axis. |
| Transcript models/parsing | **Redesign** | Closed app enum, local `Path`, exact cwd, full-tree scans, and combined fallback parsing do not survive more providers/nodes. |
| Source runtime adapters | **Keep, simplify** | Bounded inspection behind a port is useful; `SourceRef` is an optional-field union and source parsing is centralized branching. |
| Sync evaluator/queue | **Replace** | The exact-path router and global time watermark are incorrect for the target and can skip work after partial failure. |
| Durable run/event store | **Keep, redesign ownership** | Auditability is valuable, but every run is repository-owned and every spec is one of three wiki operations. |
| Detached process machinery | **Isolate by node** | Useful on one machine; PID/process-tree semantics cannot be the cross-machine core. |
| Build/Ingest/Garden workflows | **Collapse and rename** | `capture`, `curate`, and `review` better describe personal knowledge work; `build` is one-time scaffolding, not a durable domain. |
| `OperationRunner` | **Replace** | It mixes provider execution, run transitions, repo cwd, reindex, wiki validation, and completion policy. |
| Markdown wiki model | **Keep** | Human-readable local source, links, topics, frontmatter, and citations are the strongest product assets. |
| Per-repo wiki placement | **Delete for personal mode** | It fragments personal decisions and requires every work context to be a writable Git repository. |
| FTS5 derived index | **Keep, redesign partition/schema** | Rebuildable local search is correct; the schema needs vault/scope/source/location identity. |
| Cross-wiki tables | **Delete until used** | The schema exists, but page loading always emits `cross_wiki_links=()`. |
| launchd-only scheduler default | **Redesign** | It directly contradicts Windows/WSL/Linux support. |
| Codex/Claude setup hooks | **Generalize carefully** | Instruction installation is useful, but local LLMs and remote collectors need manifests/adapters, not more central enum branches. |

## Major findings

### 1. `Repository` is not a reusable domain boundary

**Finding:** `Repository` is the contaminating abstraction. It bundles identity, local path, wiki path, and operational containment.

**Evidence:**

- `Repository` carries `root_path`, fixed `almanac_root`, and derived `almanac_path` (`src/codealmanac/services/repositories/models.py:21-44`).
- `DEFAULT_ALMANAC_ROOT` is literally `Path("almanac")`, and any other root is rejected (`src/codealmanac/services/repositories/roots.py:6-30`).
- Repository identity is a hash of the normalized local absolute path (`src/codealmanac/services/repositories/identity.py:20-22`).
- The persistence schema makes both name and local root path globally unique (`src/codealmanac/services/repositories/tables.py:4-6`).
- Selection for operations requires an exact registered cwd when no name is given (`src/codealmanac/services/repositories/service.py:99-115`).
- Path validation defines safety as containment under this one local root (`src/codealmanac/services/repositories/service.py:138-146`).

**Why it exists today:** The declared product is a repo-local codebase wiki. `CLAUDE.md:8`, `CLAUDE.md:47`, `CLAUDE.md:115`, and `CLAUDE.md:134` all make this constraint explicit.

**Why it is no longer good enough:** The same project can appear as:

- `C:\src\acme` in Windows
- `/mnt/c/src/acme` in WSL
- `/home/user/acme` on Linux
- `/srv/acme` on `ssh://buildbox`
- a non-code conversation with no repository at all

Hashing the local path creates a different "repository" for every location. Exact path equality does not even assign a transcript started in a nested directory. A personal decision can also span several repositories or no repository.

**Recommendation - Redesign:**

Replace the boundary with:

```python
vault = Vault(id="personal", root=Path(".../work-almanac"))

scope = Scope(
    id="acme-platform",
    kind="project",
    title="Acme Platform",
)

location = Location(
    id="workstation-wsl",
    node_id="workstation",
    os="linux",
    transport="local",
)

alias = WorkspaceAlias(
    scope_id=scope.id,
    location_id=location.id,
    root="/mnt/c/src/acme",
    git_remote="github.com/acme/platform",
)
```

`Vault` owns the knowledge tree. `Scope` classifies knowledge. `Location` names an execution environment. `WorkspaceAlias` maps provider cwd/path/git facts to a scope. Repository metadata becomes one optional kind of evidence, not the parent of the whole application.

**Keep:** SQLite persistence mechanics, typed requests, explicit selection errors, path-containment checks inside a location adapter.

**Delete:** fixed `almanac_root` validation from the core model, path-derived global identity, and the requirement that all work has a repository.

**Risk:** Scope resolution can become over-clever. Start with explicit aliases plus git-remote fingerprints and longest-ancestor matching. Do not introduce fuzzy or model-based routing until unresolved cases prove it necessary.

**Confidence:** High.

### 2. Transcript discovery has the right seam and the wrong identity model

**Finding:** `TranscriptDiscoveryAdapter` is a real seam, but the contracts around it assume two local desktop apps and local filesystem identity.

**Evidence:**

- The port is clean and provider-facing (`src/codealmanac/services/sources/ports.py:15-22`).
- The default adapter list contains only Claude and Codex (`src/codealmanac/integrations/sources/transcripts/__init__.py:16-20`).
- `TranscriptApp` is a closed enum with only `CLAUDE` and `CODEX` (`src/codealmanac/services/sources/models.py:40-42`).
- Discovery accepts one `home: Path`; candidates contain a local `transcript_path: Path` and `cwd: Path` (`src/codealmanac/services/sources/requests.py:21-24`, `src/codealmanac/services/sources/models.py:106-112`).
- Claude and Codex roots are hard-coded as `.claude/projects` and `.codex/sessions` (`integrations/sources/transcripts/claude.py:14`, `codex.py:15`).
- Discovery recursively enumerates all JSONL files every time (`integrations/sources/transcripts/jsonl.py:9-12`).
- Subagent transcripts are deliberately excluded (`claude.py:30-31`, `codex.py:32-33`).
- Raw provider paths are converted immediately through the current platform's `Path` normalization (`jsonl.py:58-72`).

**What is reusable:**

- one adapter per provider/source format
- provider-specific metadata extraction
- typed normalization of messages/tool calls/events
- bounded reading
- explicit malformed-record fallback
- the architecture tests that keep discovery, parsing, rendering, and orchestration separate (`tests/test_architecture.py:1273`, `tests/test_architecture.py:1319`)

**What must change:**

```python
class ActivitySource(Protocol):
    source_type: str            # open identifier, not central enum

    def discover(self, cursor: Cursor) -> DiscoveryBatch: ...
    def read(self, ref: ActivityRef, after: Cursor | None) -> ActivitySlice: ...

class ActivityRef:
    source_type: str
    source_instance: str        # codex@workstation-wsl
    external_id: str            # provider session/thread id
    location_id: str
    locator: str                # provider-owned opaque locator/URI
```

Normalize provider output into a common activity envelope, not a common fake JSONL schema:

```python
ActivitySession(
    ref=...,
    started_at=...,
    updated_at=...,
    workspace_hint=WorkspaceHint(cwd=..., git_remote=...),
    actors=(...),
    events=(Message(...), ToolCall(...), ToolResult(...)),
)
```

Provider-specific adapters should own provider-specific fields. Local LLM support may come from OpenAI-compatible server logs, an explicit transcript export, or an agent wrapper; these are different source adapters, not one `LOCAL_LLM` enum branch.

**Subagent judgment:** Do not discard subagent work at discovery time. Preserve parent/child identity and let capture policy decide whether helpers are summarized into the root session. The existing Yoke event projector already models root/helper actors, proving the product can represent this relationship (`integrations/harnesses/yoke/events.py`).

**Truncation judgment:** Replace "last 60,000 characters" (`transcripts/runtime.py:15`, `transcripts/rendering.py:60-68`) with cursor-based slices and explicit event budgets. Tail-only truncation can omit the user's original goal and early decisions - the exact context a Work Almanac should retain.

**Recommendation - Keep seam, redesign contracts.**

**Confidence:** High.

### 3. Current sync is not a sync protocol

**Finding:** `SyncWorkflow` is a periodic scan plus queue operation, not a reliable multi-source sync boundary.

**Evidence:**

- Transcripts are routed only when normalized transcript cwd exactly equals a registered repository root (`workflows/sync/evaluation.py:61-68`).
- Anything else becomes `unregistered-cwd`, including nested directories and equivalent Windows/WSL/SSH paths (`evaluation.py:68`).
- The cursor is one global `last_completed_at` timestamp (`sync/models.py:18-19`, `sync/store.py:17-43`).
- The watermark is advanced after queue/spawn attempts even when individual queues fail or the worker fails to spawn (`sync/queue.py:35-67`).
- The state is not keyed by provider, source instance, location, session, or repository (`sync/tables.py:2-5`).
- A sync item turns local transcript paths back into string addresses (`sync/queue.py:75-84`), losing structured identity.

**Architectural cost:** Adding another source means more scanning and more timestamp comparisons. Adding another machine requires either mounting foreign homes or copying files. Partial failure can advance the only watermark past unprocessed work. Renamed/moved transcript files have no stable acknowledgment identity.

**Recommendation - Replace, do not extend.**

Use a source-cursor/receipt model:

```python
batch = source.discover(cursor_store.read(source.instance_id))

for item in batch.items:
    receipt = capture.accept(item.ref, item.version)
    if receipt.already_applied:
        continue
    activity = source.read(item.ref, after=receipt.cursor)
    scope = scope_resolver.resolve(activity.workspace_hint)
    result = curator.absorb(activity, scope, vault)
    receipts.commit(item.ref, item.version, result.commit_id)

cursor_store.advance(source.instance_id, batch.next_cursor)
```

Required invariants:

- idempotency key is `(source_instance, external_id, source_version)`
- source cursor advances only after all required durable receipts are committed
- failures are recorded per item and are retryable
- location and provider identity are never inferred from a bare path
- one source's failure cannot block or skip another source
- SSH collection happens through a location adapter or collector process, not a shared SQLite database

**Keep:** separation between evaluation and effects is good. Preserve that pattern as `CapturePlanner` and `CaptureExecutor`.

**Delete:** exact-path grouping, global timestamp watermark, and `transcript:<local path>` as durable identity.

**Confidence:** High.

### 4. Source adapters are useful, but `SourceRef` is an optional-field union

**Finding:** `SourcesService` correctly delegates runtime inspection, but the core source model is closed and weakly typed.

**Evidence:**

- `SourcesService.inspect_runtime()` selects the first supporting adapter (`services/sources/service.py:49-57`).
- `SourceRuntimeAdapter` is a small, honest port (`services/sources/ports.py:25-30`).
- `SourceRef` stores many mutually exclusive optional fields - path, URL, repository, number, revision range, transcript, existence, fingerprint (`services/sources/models.py:54-68`).
- Central address parsing branches on hard-coded prefixes and URL schemes (`services/sources/address_resolution.py:15-28`).
- Runtime context requires ignored directories to be repo-relative (`services/sources/requests.py:34-66`).

**Recommendation - Keep adapter registry, redesign references.**

Use discriminated reference types or an opaque locator plus adapter-owned validation:

```python
SourceRef(
    source_type="codex.session",
    source_instance="codex@workstation",
    external_id="019f...",
    locator="codex-session://workstation/019f...",
)
```

The core should know stable identity, instance, version, and provenance metadata. It should not carry every provider's optional fields. GitHub/web/file adapters remain useful optional evidence readers, but they are not required to prove the first Work Almanac value proposition.

**Simplification candidate:** Defer automatic GitHub/web/directory ingestion if transcript capture already points to durable decisions. Preserve the seam, not all machinery.

**Confidence:** High.

### 5. The durable run ledger is worth preserving; the run domain is not

**Finding:** Runs provide valuable observability for autonomous capture, but their ownership and dispatch are fixed to the old product.

**Evidence:**

- Every `RunRecord` requires `repository_id` (`services/runs/models.py:82-105`).
- `RunKind` is fixed to `BUILD`, `INGEST`, and `GARDEN` (`services/runs/models.py:22-25`).
- `RunSpec` validation bakes in the payload rules for those three kinds (`services/runs/models.py:170-204`).
- `RunExecutor` dispatches with an `if` chain over those kinds and reconstructs repository cwd (`workflows/run_queue/executor.py:43-80`).
- The run store is already split into tables, transitions, events, queries, streaming, and worker locks, and architecture tests enforce this (`tests/test_architecture.py:1661`).
- Worker/executor process control is local PID/process-tree machinery using `psutil` (`integrations/runs/process.py:44-87`, `128-175`).

**User/product value:** A personal system that automatically summarizes work needs to answer: what was captured, by which model, from which source, what changed, and why did it fail? The run/event ledger pays rent.

**Recommendation - Keep the ledger, redesign the job contract.**

```python
Job(
    id=...,
    kind="capture" | "curate" | "review" | "reindex",
    scope_id=... | None,
    location_id=...,
    source_refs=(...),
    status=...,
)
```

Move kind-specific payloads into versioned command records owned by each workflow. Do not build a generic plugin dispatcher yet; a small command registry in the composition root is enough.

Keep `psutil` execution as a local-node adapter. Add platform schedulers (Windows Task Scheduler, systemd user timer, launchd) behind the existing `SchedulerAdapter`; do not pretend one process controller spans SSH nodes.

**Simplify:** One worker per node with SQLite ownership is enough initially. Do not design a distributed queue. SSH can invoke a remote collector and return a batch to the vault-owning node.

**Confidence:** High.

### 6. `OperationRunner` is a repository-wiki transaction disguised as general orchestration

**Finding:** The name "OperationRunner" overclaims generality.

**Evidence:**

- It always derives a `Repository` from the run (`workflows/operations/service.py:57-67`).
- It always runs the harness at `repository.root_path` (`service.py:91-99`).
- After the agent finishes, it always refreshes that repository's index and validates that repository's wiki (`service.py:144-152`).
- Build, ingest, and garden all pass a git commit policy (`workflows/build/service.py:116`, `ingest/service.py:140`, `garden/service.py:109`).
- The commit policy only allows `almanac/**/*.md` and `almanac/topics.yaml`, and instructs the agent to run git from the repository root (`workflows/operations/commit.py:3-13`, `38-41`).

**Recommendation - Replace with two narrower boundaries:**

```python
agent_result = author.run(
    AuthorRequest(
        workspace=vault.root,
        prompt=...,
        source_refs=...,
    )
)

commit = vault_writer.commit(author_result.changes)
index.refresh(vault)
health.validate(vault)
jobs.finish(job, commit=commit)
```

The agent invocation boundary should know model/provider/tools. The knowledge transaction should know allowed vault mutations, validation, indexing, and optional vault-level version control. Neither should require a code repository.

**Delete/rename:**

- `BuildWorkflow` becomes `vault.initialize()` and should not require an agent unless importing an existing corpus.
- `IngestWorkflow` becomes `CaptureWorkflow`.
- `GardenWorkflow` splits into deterministic `health/repair` and agentic `curate/review`; do not make routine integrity checks invoke a model.
- `OperationRunner` should not survive under the same name.

**Confidence:** High.

### 7. Markdown and FTS5 are the strongest reusable product boundaries

**Finding:** The wiki/index subsystem contains the most valuable reusable architecture.

**Evidence:**

- Frontmatter is parsed and validated into typed page/source models (`wiki/frontmatter.py:27-48`, `54-89`).
- Markdown links are parsed structurally with `markdown-it`, not regex (`wiki/links.py:4-18`).
- Documents use content hashes (`wiki/documents.py:21-50`).
- Headings are projected into sections (`wiki/sections.py:26`).
- FTS5 is section-based (`index/schema.py:87-94`) and search uses weighted BM25 (`index/search_views.py:68`).
- The derived index stores a source signature and can be rebuilt from Markdown (`index/projection.py:10-49`, `index/sources.py:24-45`).
- The declared philosophy correctly keeps FTS5 before speculative vectors (`CLAUDE.md:148`).

**Recommendation - Keep:**

- one local Markdown vault as canonical truth
- ordinary Markdown links
- frontmatter topics and source citations
- content-hash signatures
- section projection, backlinks, topic graph
- rebuildable SQLite FTS5
- health checks as deterministic validation

**Redesign:**

- `PageSourceType` is a closed enum (`wiki/models.py:13-21`). Replace it with an open source type plus stable source reference.
- File references are case-folded and interpreted relative to one repository (`wiki/paths.py:11-16`). Evidence needs `(location_id, workspace_alias_id, relative_path)` or a stable URI.
- `IndexService` partitions state by `repository_id` and writes one `index.db` per repository (`index/service.py:30-124`, `index/schema.py:125-126`). A personal vault should have one index per vault, with `scope_id`, provider, source, location, and event time as filterable fields.
- `cross_wiki_links` should be deleted for now: the table exists, but page loading always sets `cross_wiki_links=()` (`wiki/documents.py:49`). A single vault with scopes removes the need.
- Bundled manuals copied into every `almanac/manual/` are product documentation, not personal knowledge. Keep them as installed package resources or one reserved vault help area; do not duplicate them per scope.

**Index target:**

```sql
pages(page_id, path, title, summary, body, scope_id, created_at, updated_at)
page_sources(page_id, source_instance, external_id, version, locator, captured_at)
page_locations(page_id, location_id, workspace_alias_id, relative_path)
page_links(source_page_id, target_page_id)
page_topics(page_id, topic_id)
fts_sections(page_id, section_id, title, heading, body)
```

Keep the index derived. The receipts/cursors/job ledger are runtime truth and belong in the local state database, not the Markdown index.

**Confidence:** High.

### 8. Cross-platform support is topology, not path syntax

**Finding:** Platform support cannot be achieved by teaching `normalize_path()` more path formats.

**Evidence:**

- `normalize_path()` is simply `Path.expanduser().resolve(strict=False)` on the current host (`core/paths.py:28-29`).
- App construction unconditionally defaults to `LaunchdSchedulerAdapter` (`app.py:202`).
- That adapter shells out to `launchctl` and writes plists (`integrations/automation/scheduler/launchd.py:26-41`, `68-106`).
- Setup targets and harness kinds are both closed to Codex and Claude (`services/setup/models.py:17-19`, `services/harnesses/kinds.py:4-12`).
- Detached workers use local subprocesses, PIDs, and process birth times (`integrations/runs/process.py`).

**Recommendation - Redesign around nodes:**

```python
Node(
    id="desktop-windows",
    os="windows",
    transport="local",
    capabilities={"codex", "claude", "task-scheduler"},
)

Node(
    id="gpu-linux",
    os="linux",
    transport="ssh",
    capabilities={"ollama", "systemd-user"},
)
```

One node owns the vault and runtime database in v1. Other nodes are collectors invoked over SSH or explicit export/import. Do not place SQLite on a cross-OS shared filesystem. Do not canonicalize Windows and POSIX paths into one string. Map their location-qualified aliases to the same scope.

Scheduler selection belongs in the composition root:

```python
scheduler = scheduler_for(platform.system())
# WindowsTaskSchedulerAdapter | SystemdUserAdapter | LaunchdAdapter
```

Local LLM support belongs behind either:

- an author/inference adapter, if it writes/curates knowledge, or
- an activity-source adapter, if its existing sessions are being captured.

Those are separate roles. "Which agent produced the work?" and "which model writes the Almanac?" must not share one enum.

**Confidence:** High.

## Proposed target boundaries

```text
app/
  composition.py

domain/
  vaults/          canonical Markdown location and write policy
  scopes/          projects/clients/topics and workspace aliases
  activities/      normalized sessions, actors, events, source refs
  knowledge/       pages, citations, links, topics
  jobs/            durable capture/curate/review job ledger

workflows/
  capture/         discover -> read -> resolve scope -> absorb -> receipt
  curate/          consolidate/rewrite durable knowledge
  review/          inspect proposed vault diff or health findings
  reindex/         deterministic derived-index refresh

ports/
  activity_sources.py
  author.py
  scheduler.py
  remote_node.py

integrations/
  activity_sources/
    codex/
    claude/
    openai_compatible/
    transcript_export/
  authors/
    codex/
    claude/
    openai_compatible/
  schedulers/
    windows_task_scheduler.py
    systemd_user.py
    launchd.py
  remote/
    ssh.py

storage/
  markdown_vault.py
  knowledge_index.py
  runtime_store.py
```

The main flow should read like this:

```python
batch = activities.discover(source_instance)
plan = capture.plan(batch, scope_registry, receipts)
result = capture.execute(plan, author, vault)
receipts.commit(result.applied)
index.refresh(vault)
```

This is ports-and-adapters plus a functional-core/imperative-shell split:

- provider parsing, scope resolution, cursor planning, and change validation are explicit decisions
- filesystem, SSH, schedulers, model execution, and SQLite are mechanisms behind ports
- Markdown remains the product's durable artifact

## What to delete before adding new providers

1. The belief that every durable item belongs under a code repository.
2. Exact-cwd routing in sync.
3. The global sync timestamp as the only checkpoint.
4. `transcript:<path>` as a durable source identity.
5. Cross-wiki index machinery that has no producer.
6. `BuildWorkflow` as an agent-run lifecycle.
7. Git commit policy from the generic agent execution boundary.
8. Fixed provider enums in shared domain models.
9. launchd as a universal default.

These deletions are architectural, not necessarily immediate file deletions. Their contracts should be frozen and replaced rather than expanded.

## What not to build yet

- a hosted service
- a distributed queue
- vector search
- fuzzy AI scope assignment
- bidirectional synchronization between many Markdown vaults
- a generic plugin marketplace
- a universal parser for arbitrary local-LLM logs
- automatic raw-transcript copying into the vault

The last item is a safety boundary. Agent transcripts routinely contain file contents, credentials, customer data, and tool outputs. Store stable source references and curated/redacted durable knowledge. Keep raw sources in their provider-owned location unless the user explicitly enables encrypted archival.

## Migration order

1. Introduce `Vault`, `Scope`, `Location`, `WorkspaceAlias`, and `ActivityRef` without changing current commands.
2. Make the current repository registry an adapter that produces a scope plus one local workspace alias.
3. Add per-source receipts/cursors and run current Claude/Codex discovery through them.
4. Move transcript-to-scope routing off exact cwd and onto location-qualified aliases.
5. Split agent invocation from vault mutation/index/health completion.
6. Move to one personal vault and one derived index; keep repo-local mode only if it remains an explicit product mode with an owner.
7. Add Windows/systemd schedulers and an SSH collector.
8. Add one concrete local-LLM source format only after identifying its actual log/export contract.

## Files inspected

Architecture and product rules:

- `CLAUDE.md`
- `MANUAL.md`
- `.agents/skills/deep-refactor-audit/SKILL.md`
- `tests/test_architecture.py`

Composition and platform:

- `src/codealmanac/app.py`
- `src/codealmanac/settings.py`
- `src/codealmanac/core/paths.py`
- `src/codealmanac/database/local.py`
- `src/codealmanac/database/sqlite.py`
- `src/codealmanac/integrations/automation/scheduler/launchd.py`
- `src/codealmanac/integrations/runs/process.py`
- `src/codealmanac/integrations/setup/codex.py`
- `src/codealmanac/integrations/setup/claude.py`
- `src/codealmanac/services/automation/{ports,service,selection}.py`
- `src/codealmanac/services/setup/models.py`

Repository boundary:

- all Python modules under `src/codealmanac/services/repositories/`

Sources and transcripts:

- all Python modules under `src/codealmanac/services/sources/`
- all Python modules under `src/codealmanac/integrations/sources/transcripts/`
- `src/codealmanac/integrations/sources/__init__.py`
- `src/codealmanac/integrations/sources/runtime.py`
- source adapters under `integrations/sources/{filesystem,git,github,web}/adapter.py`

Harnesses, runs, and workflows:

- `src/codealmanac/services/harnesses/{kinds,models,ports,service}.py`
- `src/codealmanac/agents/catalog.py`
- `src/codealmanac/agents/yoke.yaml`
- `src/codealmanac/integrations/harnesses/yoke/{adapter,events,results}.py`
- key modules under `src/codealmanac/services/runs/`
- key modules under `src/codealmanac/workflows/run_queue/`
- all modules under `src/codealmanac/workflows/sync/`
- `src/codealmanac/workflows/operations/{service,models,requests,harness,commit}.py`
- `src/codealmanac/workflows/{build,ingest,garden}/service.py`

Wiki and index:

- key modules under `src/codealmanac/services/wiki/`, including models, service, documents, frontmatter, links, paths, templates, topics, and sections
- key modules under `src/codealmanac/services/index/`, including models, service, store, schema, projection, sources, query, search views, and page views

## Final judgment

Do not "generalize CodeAlmanac" by adding `LOCAL_LLM`, `WINDOWS`, and `SSH` branches to the existing enums. That path will produce a larger codebase-wiki tool, not a personal Work Almanac.

Preserve the excellent local artifact model, index, typed adapters, and run observability. Replace the repository-centered domain with a vault-centered domain and make environment/provider identity explicit. Once that center moves, Codex, Claude, local LLMs, Windows, WSL, Linux, and SSH become additive adapters instead of exceptions.
