# Feature Skeptic and Hand-Rolled Machinery Report

## Goal

Critically audit CodeAlmanac's feature surface and custom infrastructure to
decide what should be preserved, simplified, deleted, redesigned, or deferred
when turning it into a personal Work Almanac that can collect work from Codex,
Claude, local LLMs, Windows, WSL, Linux, and SSH hosts.

Non-goals:

- Do not modify production code.
- Do not preserve a feature merely because tests currently freeze it.
- Do not design a hosted multi-user product.

## Executive verdict

Do not extend the current product sideways. Shrink it first.

CodeAlmanac is a well-tested local codebase-wiki product, but the requested
Work Almanac is organized around a different unit of truth:

- CodeAlmanac's unit is a **registered repository with an `almanac/` child**.
- Work Almanac's unit is a **work event/session that may belong to a project,
  system, decision, procedure, or unfinished thread**.

That is not a branding change. It invalidates the fixed repo root, exact local
path identity, repo-by-repo wiki registry, Git-only provenance assumptions,
Codex/Claude-only source catalog, and macOS-only automation path.

The current implementation has 388 package files, about 20,283 Python lines,
47 test files, and 483 test functions. The CLI advertises 20 top-level
commands, while its parsers contain 39 `add_parser` calls and 114
`add_argument` calls. There are 112 plan documents and 137 Python-port slice
documents. This is mature surface area, but it is too much inherited product
for a personal fork's first useful loop.

The right first product is:

```text
work event
  -> normalize source/host/project/time
  -> redact or reject sensitive material
  -> append to a local inbox/outbox
  -> AI distills durable knowledge
  -> write/update Markdown in one personal vault
  -> rebuild a derived SQLite search index
```

Everything else has to prove it helps that loop.

## Current product surface

The public command catalog is frozen in
`src/codealmanac/cli/parser/root.py:11-14`:

```text
init ingest garden sync list search show topics health validate reindex
serve tag untag config setup uninstall doctor update jobs automation
```

The catalog then duplicates a large amount of command help and recovery text in
`src/codealmanac/cli/syntax/catalog.py`; that custom syntax subsystem alone is
456 lines across four files. The application composition root wires 20 named
services and five workflows in `src/codealmanac/app.py`.

Large feature clusters include:

| Cluster | Approximate owned size | Current value for Work Almanac |
|---|---:|---|
| CLI | 3,996 Python lines | Necessary edge, far too broad |
| Services | 9,569 Python lines | Some valuable core, much product baggage |
| Integrations | 3,805 Python lines | Valuable seam, wrong default set |
| Run service + run queue | 2,296 Python lines | Durable receipts useful; implementation oversized |
| Viewer/server | 752 Python lines plus ~3,100 static lines | Nice later; not core |
| Setup + automation | 1,512 Python lines | Mostly wrong for cross-platform personal use |
| Telemetry | 555 Python lines | No value in a private fork |
| Self-update | 380 Python lines including integration | Distribution concern, not product core |
| Sync | 465 Python lines | Concept valuable; current identity/checkpoint model wrong |

## Product capabilities that should survive

### Keep: Markdown as durable, inspectable truth

This is the strongest part of the product. Plain Markdown is human-readable,
Git-friendly, agent-readable, and survives the application. The trust model in
`CLAUDE.md` and the committed wiki tree are good foundations.

For Work Almanac, keep Markdown but move from one wiki per code repository to
one personal vault with explicit project/system provenance:

```text
work-almanac/
  daily/
  projects/
  decisions/
  problems-and-solutions/
  systems/
  procedures/
  unfinished/
```

Do not require every source project to contain its own `almanac/`. The fixed
root is enforced in `src/codealmanac/services/repositories/roots.py:6-29` and
explicitly frozen by `tests/test_public_contract.py:188-197`; that contract is
the wrong product contract now.

### Keep: a derived SQLite read model

FTS, backlinks, source references, and health checks are legitimate complexity
for a growing personal knowledge base. SQLite should remain rebuildable from
Markdown. It should not become the only copy of captured knowledge.

Keep:

- FTS-backed text search.
- Page/source linkage.
- Backlinks.
- A rebuildable index.
- Basic validation of page identity and source records.

Simplify:

- Flatten the topic DAG into frontmatter fields or flat tags for the first
  Work Almanac version.
- Treat `kind`, `project`, `system`, `host`, `status`, and `observed_at` as
  first-class facets rather than encoding all classification in topics.

### Keep: source adapters as a seam

`SourcesService` and `SourceRuntimeAdapter` are honest seams
(`src/codealmanac/services/sources/service.py`). Files, Git diffs, commits, and
agent transcripts are all useful Work Almanac evidence.

Do not keep the current catalog as product policy. The default runtime adapter
list in `src/codealmanac/integrations/sources/__init__.py:12-19` eagerly includes
filesystem, Git, GitHub, transcripts, and web. Work Almanac first needs:

1. explicit note/text,
2. file/directory,
3. Git change,
4. agent transcript,
5. normalized shell/session event.

GitHub and arbitrary web ingestion should be deferred until the core
cross-environment capture loop works.

### Keep: AI judgment in prompts

The existing "ingest" and "garden" distinction is sound:

- ingest decides what durable knowledge a source contains;
- garden reconciles duplicates, stale knowledge, and weak structure.

Rename them for the personal product only if user language benefits:

```text
capture/absorb  -> turn evidence into durable work knowledge
garden          -> reconcile the personal vault
```

Avoid building rules that attempt to infer decisions, incidents, and next steps
from command strings. The model should make that judgment from normalized
evidence.

## Strongest feature objections

## 1. The repository is the wrong aggregate

### Evidence

`Repository` requires a `root_path`, a fixed `almanac_root`, and an
`almanac_path` equal to `root_path / almanac_root`
(`src/codealmanac/services/repositories/models.py:21-47`).
Registration and lookup persist exact local filesystem paths
(`src/codealmanac/services/repositories/store.py:20-68`).
Operations without `--wiki` require the exact current directory to be a
registered repository root
(`src/codealmanac/services/repositories/service.py:90-110`).

### Why that is no longer good enough

One project may appear as:

```text
C:\Users\user\Documents\my-service
/mnt/c/Users/user/Documents/my-service
/home/user/my-service
/srv/my-service
```

Exact resolved paths do not provide stable identity across Windows, WSL,
containers, SSH hosts, or clones. Some work is not in a Git repository at all.

### Recommendation: redesign

Replace the repository aggregate with:

```text
Vault          one personal knowledge tree
Project        stable user-level identity, optional repository links
Environment    host + OS/shell/runtime identity
Source         evidence captured from an environment
WorkSession    related events with a purpose and outcome
```

A source can optionally point to a repository remote, commit, branch, and local
path. None of those should be the project's sole identity.

Confidence: high.

## 2. "Which agent produced evidence?" is conflated with "Which model writes the wiki?"

### Evidence

Both the lifecycle harness and transcript-source enums are closed:

- `HarnessKind` is only `codex | claude` in
  `src/codealmanac/services/harnesses/kinds.py:4-6`.
- `TranscriptApp` is only `claude | codex` in
  `src/codealmanac/services/sources/models.py:40-42`.
- setup targets are hard-coded to Codex and Claude in
  `src/codealmanac/services/setup/requests.py:16-21`.
- config validates a short, centrally controlled model catalog in
  `src/codealmanac/services/config/models.py:24-51`.

### Architectural cost

Adding a local LLM currently cuts through parser choices, config validation,
telemetry validation, setup, readiness, Yoke construction, transcript
discovery, tests, and documentation. More importantly, it assumes the agent
that performed work must also be a supported summarization provider.

### Recommendation: redesign

Separate:

```text
SourceProducer = codex | claude | aider | shell | ssh | local-agent | manual
Distiller       = configured callable agent/model used to write the vault
```

Producer identity should be open text plus optional adapter metadata.
Distillers can remain a small set of configured runners. A local LLM can first
arrive as a distiller command adapter without teaching every source type about
it.

The generic source/runtime port is worth keeping; the closed enums are not.

Confidence: high.

## 3. Automation is a macOS product feature pretending to be a general seam

### Evidence

- README says only macOS is supported
  (`README.md:24`) and setup installs three `launchd` jobs
  (`README.md:60-61`).
- `create_services` always constructs `LaunchdSchedulerAdapter` when no test
  adapter is supplied (`src/codealmanac/app.py`).
- `LaunchdSchedulerAdapter` emits plists and parses `launchctl print` prose
  (`src/codealmanac/integrations/automation/scheduler/launchd.py`).
- CLI rendering itself says `launchd loaded`
  (`src/codealmanac/cli/render/automation.py:29`).
- Package metadata nevertheless declares `Operating System :: OS Independent`
  (`pyproject.toml:19`), and a test freezes that contradiction
  (`tests/test_public_contract.py:167`).

### Recommendation: delete the managed scheduler for MVP

Make these commands deterministic and foreground-capable:

```text
wa collect
wa sync
wa garden
```

Document how users call them from Task Scheduler, cron/systemd timers, or
launchd. Do not own scheduler installation, status parsing, and platform UI
until there is evidence the manual integration is the product bottleneck.

If managed scheduling later earns its place, keep a `SchedulerAdapter` seam and
add platform-specific adapters. Do not make one platform adapter the default on
every OS.

This deletes or freezes:

- `automation` CLI group,
- automation config keys,
- setup interval flags,
- `LaunchdSchedulerAdapter`,
- launchd-specific output,
- background-item onboarding screens,
- scheduled self-update.

Confidence: high.

## 4. Setup has become a second product

### Evidence

`setup` exposes target selection, runner selection, prompt mode, auto-commit,
telemetry, instruction installation, auto-update, sync and garden intervals,
sync/garden disabling, and JSON output
(`src/codealmanac/cli/parser/setup.py`). Setup then mutates global
`~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, user config, automation, and
package state through multiple install/uninstall adapters.

The setup service and integration cluster is roughly 941 Python lines, before
CLI wizard/rendering code.

### Why this does not pay rent in a personal fork

The user needs a place that captures work across agents, not an installer that
teaches exactly two agents a codebase-wiki manual. Global instruction mutation
also becomes more dangerous when the product stores personal work rather than
repo-local architecture notes.

### Recommendation: replace with explicit bootstrap

For MVP:

```text
wa init <vault-path>
wa doctor
```

`init` writes a minimal config and vault scaffold. Agent instruction snippets
are printed or copied on explicit request. Do not silently or automatically
modify global Codex/Claude instruction files.

Keep uninstall only if the tool is distributed to other people. For a personal
fork, deletion instructions in a README are enough.

Confidence: high.

## 5. The durable job concept is valid; the current queue is not proportionate

### Evidence

The run subsystem owns durable records, specs, events, status transitions,
worker locks, attach polling, cancellation, process identity, process-tree
suspension/termination, worker spawning, executor spawning, and viewer
projection:

- 1,749 lines in `services/runs`;
- 547 lines in `workflows/run_queue`;
- worker and executor subprocesses created with `start_new_session=True`
  (`src/codealmanac/integrations/runs/process.py:28-100`);
- process trees are suspended, enumerated, resumed, terminated, and killed
  with `psutil` in the same file;
- `RunAttachStreamer` polls SQLite and sleeps
  (`src/codealmanac/services/runs/streaming.py:15-50`);
- hidden CLI commands `__run-worker`, `__run-executor`, and
  `__garden-scheduler` are registered in
  `src/codealmanac/cli/parser/run_commands.py`.

### User/product value

A receipt saying "this source was accepted, processed, failed, or needs
attention" is valuable. A durable outbox is also important when an SSH host
cannot reach the central vault.

### Recommendation: redesign and defer cancellation machinery

Phase 1 should run capture/distillation synchronously and write a small durable
receipt:

```text
capture_id
source_id
status = pending | processed | failed
attempted_at
error_summary
```

Phase 2 may introduce a standard single-process queue or database-backed worker
after asynchronous capture is proven necessary. Keep idempotency and durable
receipts. Delete or defer:

- two-level worker/executor spawning;
- process-tree suspension;
- live attach polling;
- rich harness event projection;
- job cancellation;
- jobs viewer dashboard.

Do not replace this with Celery/Redis; that would be worse for a local personal
tool. A SQLite outbox claimed transactionally by one worker is sufficient.

Confidence: high.

## 6. Sync's current identity and checkpoint semantics cannot support multiple environments

### Evidence

Transcript sync maps a transcript to a repository with an exact normalized path
dictionary
(`src/codealmanac/workflows/sync/evaluation.py:61-67`). It reads transcript
stores only under the current `Path.home()`
(`src/codealmanac/workflows/sync/evaluation.py:48`). The state store has one
global row named `"sync"` with one `last_completed_at`
(`src/codealmanac/workflows/sync/store.py`).

More seriously, sync records the global checkpoint even after individual queue
failures or worker-spawn failure
(`src/codealmanac/workflows/sync/queue.py:31-67`). That can advance the scan
window past evidence that was never processed.

### Recommendation: redesign

Use per-source cursors and stable event IDs:

```text
collector_id = laptop/windows/codex
cursor       = provider-specific opaque position
event_id     = hash(collector_id, provider_session_id, event_sequence)
```

Only acknowledge a cursor after the central outbox durably accepts all events
up to that cursor. A failed distillation should not require re-reading the
source store; it should retry from the outbox.

Cross-host transfer must be an explicit later seam:

```text
collector -> encrypted/authenticated transport -> central inbox
```

Do not make shared filesystem paths the protocol.

Confidence: high.

## 7. Raw transcript ingestion needs a privacy boundary before expansion

### Evidence

Transcript adapters read local JSONL, render readable entries, include the
source path, and pass up to 60,000 characters to the lifecycle model
(`src/codealmanac/integrations/sources/transcripts/runtime.py`,
`src/codealmanac/integrations/sources/transcripts/rendering.py`).
`IngestWorkflow` serializes source runtime snapshots directly into the agent
prompt (`src/codealmanac/workflows/ingest/service.py`).

The harnesses run broadly and non-interactively:

- Claude uses `permission_mode="dontAsk"` and broad file/shell tools
  (`src/codealmanac/integrations/harnesses/yoke/adapter.py:172-181`);
- Codex uses `DANGER_FULL_ACCESS` and approval `NEVER`
  (`src/codealmanac/integrations/harnesses/yoke/adapter.py:184-190`).

Telemetry has careful redaction, but source ingestion does not. That is
reasonable for the existing trusted repo-local product, but unsafe as a default
for centralizing shell, SSH, and personal work across machines.

### Recommendation: redesign before adding shell capture

Introduce a collection policy before transport or AI:

```text
include: event type, time, project, command class, exit status, changed files
redact: environment values, tokens, credential-shaped strings, private keys
deny: .ssh, credential stores, secret files, raw environment dumps
raw retention: local-only, short TTL, opt-in transfer
```

Prefer source summaries and structured facts over raw terminal history. An
explicit `wa capture --include-raw` can opt into raw material for a single
event. The default must not record every keystroke or full shell output.

Confidence: high.

## 8. Topic graph editing is solving the wrong classification problem

### Evidence

The CLI has eight topic actions plus `tag` and `untag`
(`src/codealmanac/cli/parser/wiki.py`). Topic mutation uses round-trip YAML,
rewrites frontmatter across pages, prevents cycles, and maintains a graph across
many service/index modules.

### Recommendation: simplify

For Work Almanac, a document should first have a stable type and a few
facets:

```yaml
kind: decision
project: my-service
systems: [payments]
status: active
tags: [reliability, timeout]
observed_at: 2026-07-27T14:48:00+09:00
```

Folders and backlinks already provide hierarchy. Flat tags are enough until the
user repeatedly needs a curated taxonomy. Delete the topic mutation CLI and
`topics.yaml` DAG from the first reshaped version. Preserve a migration script
only long enough to convert existing pages.

Confidence: medium-high.

## 9. Viewer and jobs dashboard are polish before product truth

### Evidence

The local viewer uses FastAPI, Uvicorn, a custom Markdown renderer, a static JS
single-page app, repository switching, page/topic/file/search routes, and job
projections. It contributes a large dependency and maintenance surface:

- `fastapi` and `uvicorn`;
- roughly 752 Python lines in viewer services;
- roughly 3,100 server/static lines;
- custom citation and page-link rewriting
  (`src/codealmanac/services/viewer/renderer.py`);
- job endpoints in `src/codealmanac/server/api_routes.py`.

### Recommendation: defer, then revive only the read surface

Markdown, `wa search`, and `wa show` are enough to validate the Work Almanac
model. Obsidian, VS Code, or a plain file browser can serve as an interim UI.

If a viewer returns, make it a thin read-only projection of the vault and index.
Do not restore jobs until asynchronous jobs have earned their place.

Confidence: high.

## 10. Telemetry, self-update, and package self-uninstall should be deleted

### Evidence

Telemetry defaults to enabled
(`src/codealmanac/services/config/models.py:89-94`), ships a PostHog project key
in source (`src/codealmanac/integrations/telemetry/sender.py:13`), creates a
persistent installation identity, shapes three event families, launches a
detached sender process, and has extensive privacy tests.

Self-update detects uv/pip/editable installs, owns an update lock, checks active
runs, runs smoke commands, and schedules updates
(`src/codealmanac/services/updates/service.py`). Uninstall deletes global state,
edits global agent instructions, removes schedules, and invokes the package
manager (`src/codealmanac/services/setup/service.py`,
`src/codealmanac/integrations/setup/uninstall.py`).

### Recommendation: delete

These are open-source distribution concerns, not personal work-memory value.
They add remote behavior and destructive/global mutation to a privacy-sensitive
tool. The fork should start with:

- no PostHog dependency or outbound analytics;
- no installation UUID;
- no `update` command;
- no scheduled auto-update;
- no package self-uninstall;
- no global-state deletion command.

Use Git/uv for updating the personal checkout. Reconsider packaging only if the
tool is later distributed to others.

Confidence: high.

## Hand-rolled machinery decisions

| Machinery | Evidence | Decision |
|---|---|---|
| Custom CLI syntax classifier/catalog | `cli/syntax`, 456 lines, duplicated command prose | Delete. Use ordinary argparse help/errors or move to Typer only if a CLI rewrite is already justified. Do not adopt a framework solely for prettier errors. |
| Custom TOML line editor | `services/config/store.py:82+` updates lines/tables itself | Replace. Either write the tiny canonical config atomically or use `tomlkit` if comment preservation is a real requirement. |
| Three YAML/frontmatter paths | `python-frontmatter` + PyYAML for reads, `ruamel-yaml` for mutation | Consolidate. Use one parser/serializer, preferably ruamel only if round-trip writes remain. |
| Topic DAG and mutation engine | topic store, graph, read model, CLI mutation commands | Delete from MVP; use flat facets/tags. |
| Source address mini-language | `github:pr:`, `git:range:`, `git:diff:`, `transcript:` branches in `address_resolution.py` | Simplify. Keep a tiny explicit parser for owned syntax, but do not grow colon strings into a protocol. Typed API/event envelopes should be the cross-host boundary. |
| Detached worker/executor process queue | `workflows/run_queue`, `integrations/runs/process.py` | Redesign. One SQLite outbox + one worker later; synchronous first. |
| Process-tree cancellation | psutil suspend/resume/terminate/kill with PID birth checks | Delete/defer until users prove cancellation is required. |
| Polling attach streamer | repeated SQLite reads + `time.sleep` | Delete with live jobs. If later needed, use a simple event cursor API. |
| launchctl output parser | custom parsing of human-shaped launchd output | Delete with managed scheduler. |
| Custom local SPA/viewer | static JS routing/rendering plus FastAPI APIs | Defer. Preserve read-service seam only if cheap. |
| Custom Markdown citations | regex for `[@id]` plus link token rewriting | Defer with viewer. Prefer standard Markdown links/footnotes unless source-number citations are proven valuable. |
| Telemetry event/redaction pipeline | 555 lines plus PostHog dependency and detached sender | Delete entirely in the private fork. |
| Self-update/package detection | install metadata, package runner, locks, smoke tests | Delete entirely in the private fork. |

## Keep / simplify / delete / defer summary

### Keep

- Markdown vault as durable source of truth.
- Derived SQLite FTS index.
- Page links, backlinks, and source provenance.
- Explicit AI distillation and garden prompts.
- Source adapter boundary.
- Typed models at external boundaries.
- Git history for the central vault.
- Basic `search`, `show`, `validate`, and explicit `capture`.

### Simplify

- Repository registry -> project/environment/source records.
- Topics DAG -> flat typed facets and tags.
- Health -> schema/source/link checks that matter to Work Almanac.
- Config -> vault path, distiller, privacy policy, transport endpoint at most.
- Run history -> capture receipts/outbox.
- CLI -> approximately 6-8 core commands.
- Frontmatter/YAML stack -> one implementation.

### Delete candidates

- Telemetry and PostHog.
- Self-update and package self-uninstall.
- Managed launchd automation and setup schedule flags.
- Global Codex/Claude instruction mutation as default setup.
- Current topics mutation surface.
- Custom CLI syntax recovery.
- Jobs attach/cancel/live event machinery.
- Process-tree control.
- Viewer jobs dashboard.
- `ca` compatibility alias if the product becomes `workalmanac`/`wa`.

### Defer

- Web and GitHub source fetching.
- Rich local viewer.
- Managed cross-platform schedulers.
- Live job streaming and cancellation.
- Multi-user/hosted accounts.
- Semantic/vector search.
- Automatic shell hooks that capture every command.
- Remote raw transcript retention.

## Minimal target CLI

The first reshaped CLI should feel like:

```text
wa init [vault]
wa capture <source...> [--project NAME] [--note TEXT]
wa sync [--collector NAME]
wa search [query] [--kind KIND] [--project NAME] [--system NAME]
wa show <page>
wa status
wa garden
wa doctor
```

`sync` should mean "move durable normalized events from collector outboxes to
the vault inbox," not "scan this one machine's Codex/Claude directories and
match exact repository paths."

`status` should show collectors, pending/failed receipts, and the last
acknowledged cursor. It should replace separate `list`, `jobs`, `automation
status`, and `sync status` surfaces.

## Refactor order from the feature-skeptic view

1. Freeze new features and write the Work Almanac content/event contract.
2. Delete telemetry, self-update, scheduled update, and package self-uninstall.
3. Hide or remove viewer/jobs/automation/topic-mutation commands from the new
   product surface.
4. Introduce `Vault`, `Project`, `Environment`, `Source`, `WorkEvent`, and
   `CaptureReceipt` names without preserving repository path as identity.
5. Build explicit local capture into one vault; no background daemon yet.
6. Add a per-collector outbox and acknowledgements; test Windows/WSL path and
   identity differences.
7. Add transcript collectors for Codex and Claude behind an open producer
   identity. Add local LLM/shell producers through the same envelope.
8. Only after the end-to-end loop is trustworthy, add external scheduling and
   encrypted/authenticated SSH or HTTP transport.
9. Reintroduce a read-only viewer if CLI/Markdown browsing is genuinely
   insufficient.

## Questions the user must eventually settle

1. Is there one central private Git vault, or does every machine keep a full
   replica?
2. May raw transcripts ever leave the machine that produced them, or only
   distilled summaries and structured facts?
3. Should work unrelated to a code repository be first-class? This report
   assumes yes.
4. Is automatic capture allowed to see shell command text, or only task/session
   summaries, Git state, timestamps, and exit codes?
5. Which machine is allowed to run the distiller model and write the canonical
   vault?
6. Is `WorkAlmanac`/`wa` the desired public name, or is this permanently a
   private `MyAlmanac` fork?

## Files inspected

- `CLAUDE.md`
- `MANUAL.md`
- `README.md`
- `pyproject.toml`
- `docs/python-port-live-agreement.md`
- `src/codealmanac/app.py`
- `src/codealmanac/settings.py`
- `src/codealmanac/cli/parser/**`
- `src/codealmanac/cli/syntax/**`
- `src/codealmanac/services/config/**`
- `src/codealmanac/services/setup/**`
- `src/codealmanac/integrations/setup/**`
- `src/codealmanac/services/automation/**`
- `src/codealmanac/integrations/automation/**`
- `src/codealmanac/services/repositories/**`
- `src/codealmanac/services/sources/**`
- `src/codealmanac/integrations/sources/**`
- `src/codealmanac/services/harnesses/**`
- `src/codealmanac/integrations/harnesses/**`
- `src/codealmanac/services/runs/**`
- `src/codealmanac/workflows/run_queue/**`
- `src/codealmanac/workflows/sync/**`
- `src/codealmanac/services/viewer/**`
- `src/codealmanac/server/**`
- `src/codealmanac/services/telemetry/**`
- `src/codealmanac/integrations/telemetry/**`
- `src/codealmanac/services/updates/**`
- `src/codealmanac/integrations/updates/**`
- `src/codealmanac/services/wiki/frontmatter.py`
- `src/codealmanac/services/wiki/frontmatter_rewrite.py`
- `src/codealmanac/services/wiki/topic_file.py`
- relevant tests under `tests/`
