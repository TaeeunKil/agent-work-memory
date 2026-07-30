# Target Architect Report: A Personal Work Almanac

## Executive verdict

The requested product does not fit cleanly inside CodeAlmanac's current center.
It should not be implemented by making `repository_id` optional, adding more
transcript providers, or placing a central wiki above the existing per-repo
wikis.

CodeAlmanac currently means:

> choose one registered repository, load source material associated with that
> repository, run an agent in that checkout, and maintain `repo/almanac/`.

The requested Work Almanac means:

> observe one person's work across tools and environments, preserve enough
> evidence to understand it, group it into editable work sessions, and maintain
> one private body of durable knowledge.

That changes the aggregate root from `Repository` to `Person/Vault`, the first
stored representation from `WikiPage` to `WorkEvent`, and the ownership model
from "the Git repository owns its wiki" to "the user owns a private work
memory." Repository, branch, host, shell, agent, and SSH destination become
context attached to work; none may remain a mandatory parent.

The right migration is therefore a bounded product reset that reuses proven
mechanisms as donors:

- keep the composition-root, service/port/adapter discipline;
- keep normalized provider edges, Markdown parsing, citations, FTS5, the
  read-only viewer, and the useful parts of job observability;
- redesign repository registration as projects plus workspaces;
- redesign transcript sync as provider-neutral observation intake;
- replace per-repo lifecycle runs with vault-scoped compile jobs;
- delete repo-only workflow, launchd-only automation, public telemetry, and
  compatibility machinery that does not serve the personal product.

Do not start with shell hooks, an always-on daemon, cross-host replication, or
automatic AI gardening. Start with a privacy-safe walking slice: manual notes
and opt-in Codex/Claude transcript import, editable sessions, one private
Markdown vault, FTS search, and explicit compilation by a user-selected agent.

## Cross-audit verification

The independent boundary and feature audits completed after this design began
and support the same reset:

- the current product equates repository registration, transcript cwd, wiki
  location, run ownership, index partition, and Git boundary;
- sync uses one global time watermark and exact cwd matching, and advances its
  watermark even after some queue or worker-spawn failures;
- provider identity is closed in both capture (`TranscriptApp`) and writing
  (`HarnessKind`);
- launchd, telemetry, self-update, the full detached queue, topic mutation, and
  the jobs viewer are disproportionate to the personal MVP.

The boundary audit names the independent axes `Vault / Scope / Location /
Source`. This report realizes the same shape with `Vault`, logical `Project`
(the first concrete scope), `Host + Environment + Workspace` (location), and
`Collector + Artifact/EvidenceRef` (source). Keep `Scope` as a future seam only
if a second scope kind beyond project becomes concrete; do not build a generic
scope hierarchy now.

## Product thesis

**Work Almanac is a local-first, private memory of work, independent of which
agent, shell, repository, operating system, or host produced the evidence.**

It should answer:

- What did I work on, where, and with which tools?
- What decision did I make, why, and when should I revisit it?
- How did I solve this problem last time?
- What remains unfinished, and what is the next concrete step?
- Which work on Windows, WSL, Linux, or an SSH host was part of the same effort?
- What evidence supports this memory, and can I inspect it without trusting an
  AI summary?

It should not attempt to remember every byte forever. A useful memory system
for work needs aggressive separation between sensitive evidence and durable
knowledge.

## The four-layer model

The four layers have different authority, retention, mutability, and storage.
Collapsing any two creates either a privacy problem or a retrieval problem.

| Layer | Meaning | Persistence | Default retention | Human editing |
| --- | --- | --- | --- | --- |
| Raw events | Normalized facts a collector observed | Private local event store, optional protected blobs | Bounded and deletable | No |
| Work sessions | An editable grouping and interpretation of related events | Private structured session ledger | Retained | Yes, through explicit verbs |
| Durable knowledge | Reusable conclusions worth remembering | Private, browseable Markdown vault | Long-lived; Git optional | Yes |
| Derived indexes | Query projections over sessions and knowledge | Disposable SQLite/FTS | Rebuildable | No |

### 1. Raw event

A `WorkEvent` is "raw" relative to a session or wiki article. It is not
necessarily a byte-for-byte copy of an external transcript line. An integration
parses an external shape once, privacy policy removes or quarantines sensitive
fields, and intake persists a normalized envelope.

Core fields:

```python
class WorkEvent:
    event_id: EventId
    schema_version: int
    kind: EventKind                    # e.g. agent.turn, git.commit, note.created
    occurred_at: datetime | None       # source clock
    observed_at: datetime              # collector clock
    source: CollectorRef               # adapter + installation + source event id
    environment_id: EnvironmentId
    actor_refs: tuple[ActorRef, ...]    # human and/or software agent
    correlation: CorrelationHints      # provider session, shell session, trace, etc.
    attributes: SafeAttributes         # typed, allowlisted occurrence facts
    content: ContentRef | None          # private blob, never inline by default
    artifact_refs: tuple[ArtifactRef, ...]
```

Two timestamps are necessary because host clocks drift and import may happen
later. OpenTelemetry's stable logs model makes the same useful distinction
between `Timestamp` at the source and `ObservedTimestamp` at collection time,
and separates stable source `Resource` context from per-occurrence
`Attributes` [OpenTelemetry Logs Data
Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/).

Raw events are append-only during their retention window for auditability and
deduplication, but they are **not immutable forever**. Privacy deletion must be
able to remove content or entire events. This is a deliberate limit on the
event-sourcing analogy.

### 2. Work session

A `WorkSession` is a retained interpretation of activity, not a background
agent job and not a transcript.

```python
class WorkSession:
    session_id: SessionId
    title: str | None
    goal: str | None
    outcome: str | None
    state: Literal["open", "complete", "paused", "abandoned"]
    started_at: datetime
    ended_at: datetime | None
    event_refs: tuple[EventId, ...]
    project_refs: tuple[ProjectId, ...]
    artifact_refs: tuple[ArtifactRef, ...]
    environment_refs: tuple[EnvironmentId, ...]
    continuation_of: SessionId | None
    grouping_basis: GroupingBasis
    confidence: float | None
    user_confirmed: bool
```

Sessions may:

- span Windows and WSL;
- continue later on an SSH host;
- involve more than one repository;
- overlap in time;
- have no repository at all;
- be split, merged, or reassigned by the user without modifying raw evidence.

Sessionization should use explicit correlation first (provider session id,
shell session id, explicit `wa start`, imported bundle id), then workspace/Git
context and temporal proximity. A fixed inactivity gap alone is insufficient:
people run concurrent agents, leave terminals open, and resume work on another
machine.

When raw content expires, the accepted session record and its factual summary
remain. That makes sessions a retained intermediate layer rather than a
projection that is always reconstructible.

### 3. Durable knowledge

Durable knowledge is the only layer intended to read like a personal wiki.
It records reusable conclusions, not activity exhaust.

Suggested first tree:

```text
<private-vault>/
|-- README.md
|-- inbox/
|-- projects/
|-- decisions/
|-- problems/
|-- procedures/
|-- systems/
|-- unfinished/
`-- notes/
```

Folders express the primary reading neighborhood. Tags may cross-cut folders.
Do not carry the current `topics.yaml` DAG into the MVP; it is useful machinery
for a large codebase wiki but is not required to prove personal work memory.

Daily activity should initially be a viewer/query projection from sessions,
not thousands of generated Markdown pages competing with durable knowledge.
If users later need portable daily files, add a deterministic export under a
clearly generated namespace.

Every page needs a stable id because sessions and evidence must survive page
moves:

```yaml
---
id: mem_01K...
title: Payment request timeout decision
tags: [payments, reliability]
sources:
  - id: session-payment-timeout
    type: work-session
    ref: work://session/ses_01K...
  - id: fixing-commit
    type: git-commit
    ref: work://artifact/git/commit/a83f92c
---
```

Markdown links remain the authored link syntax. Source ids support citations
near claims. Category-specific fields are allowed when a real query needs
them—for example `status`, `decided_at`, and `revisit_when` on a decision—but a
global page-kind hierarchy is unnecessary.

### 4. Derived indexes

`index.db` is disposable and rebuilt from the Markdown vault plus the retained
session ledger. It may contain:

- page and section FTS5;
- backlinks and source references;
- session-summary FTS5;
- project, environment, date, and status facets;
- a unified result projection that keeps "session" and "knowledge" visibly
  distinct.

Raw content is excluded from normal full-text search. An explicit
`--include-raw` query may search retained evidence locally, with a warning and
no browser exposure by default.

SQLite FTS5 remains the right first retrieval mechanism. SQLite explicitly
supports contentless and external-content indexes, while making the application
responsible for consistency with the source table [SQLite FTS5
documentation](https://www.sqlite.org/fts5.html). Dense vectors should wait for
measured lexical misses.

## Target vocabulary

| Noun | Owns | Does not imply |
| --- | --- | --- |
| Vault | One person's durable knowledge and local state identity | One repository |
| Host | A physical or virtual machine identity | An OS environment |
| Environment | Windows native, a WSL distro, Linux, container, or remote runtime context | A project |
| Collector | Reads one outside activity surface and emits observations | An AI provider |
| Work event | A normalized observation accepted by privacy policy | A durable conclusion |
| Work session | Related work with a goal/outcome and evidence | A provider conversation |
| Project | A logical body of work | One checkout or Git repository |
| Workspace | One concrete path/checkout on one environment | The durable wiki owner |
| Artifact | A file, commit, PR, issue, URL, command result, or other evidence entity | Source of truth for every claim |
| Memory | One durable Markdown knowledge page | A summary of one session |
| Compile job | Agent work that updates durable knowledge | The user's work session |

The word `source` is too overloaded in the current code. Use `Collector` for
where observations arrive, `ArtifactRef` for a thing used, and `EvidenceRef`
for a citation.

## Pseudocode wireframe

This is the intended feel of the code and the main architecture review surface:

```python
# Capture: provider-specific shapes terminate at the collector.
observation = collectors.codex.read(entry)
accepted = almanac.intake.accept(
    AcceptObservation(observation, policy=privacy.capture_policy())
)

# Correlation: sessions own grouping; projects and repositories are hints.
session = almanac.sessions.attach(
    AttachEvent(
        event_id=accepted.event_id,
        hints=accepted.correlation,
    )
)

# Explicit manual correction is first-class and does not rewrite evidence.
almanac.sessions.merge(MergeSessions(primary, continuation))
almanac.sessions.assign_project(AssignProject(session.id, "my-service"))
almanac.sessions.close(CloseSession(session.id, outcome="tests pass"))

# Compile: the user chooses the evidence scope and the agent runtime.
job = almanac.memory.enqueue(
    CompileMemory(
        session_ids=(session.id,),
        runtime="codex",                    # claude/local-cli are adapters
        content_access="selected-local",
    )
)

# The writer edits only the private Markdown vault. No proposal/apply protocol.
almanac.jobs.run(job.id)

# Queries read disposable projections, not provider files.
results = almanac.search.find(
    Search(query="payment timeout", layers=("knowledge", "sessions"))
)
```

Cross-host movement is a separate, mechanical workflow:

```python
# Remote installations only export accepted event batches.
batch = remote.transport.export(after=cursor, policy="metadata-and-selected")

# Import is idempotent; it never executes a command from the remote payload.
receipt = central.transport.import_batch(batch)
central.sessions.correlate(receipt.event_ids)
central.transport.advance_cursor(receipt)
```

## Target boundaries

```text
src/workalmanac/
|-- app.py                         # composition only
|-- core/                          # ids, errors, time/path primitives
|-- database/                      # local SQLite connections/migrations
|-- services/
|   |-- vaults/                    # one private vault and its paths
|   |-- environments/              # hosts, environments, aliases
|   |-- projects/                  # logical projects and concrete workspaces
|   |-- intake/                    # event envelope, dedupe, collector port
|   |-- privacy/                   # collection/content/retention policy
|   |-- sessions/                  # grouping, merge/split, close, assignment
|   |-- knowledge/                 # Markdown truth and evidence links
|   |-- index/                     # rebuildable projections and FTS
|   |-- jobs/                      # compile/garden execution ledger
|   `-- runtimes/                  # memory-writer port and normalized events
|-- workflows/
|   |-- import_activity/
|   |-- compile_memory/
|   |-- garden_memory/
|   `-- transport/
|-- integrations/
|   |-- collectors/
|   |   |-- codex/
|   |   |-- claude/
|   |   |-- git/
|   |   |-- manual/
|   |   `-- shell/                 # later, opt-in
|   |-- runtimes/
|   |   `-- yoke/                  # first concrete writer runtime
|   |-- transport/
|   |   |-- filesystem/
|   |   `-- ssh/                   # later
|   `-- scheduling/                # later, per-platform adapters
|-- cli/
`-- server/                        # read-only local viewer
```

### Boundary rules

1. **Collectors do not choose sessions or write knowledge.** They parse outside
   formats into observations.
2. **Privacy policy runs before persistence and before model access.** It is not
   a cleanup pass after secrets have already been copied.
3. **Sessions own correlation.** Collector-specific session ids are hints, not
   the product identity.
4. **Projects do not own events or memories.** They are many-to-many labels and
   workspace mappings.
5. **Agent runtimes do not own provider policy.** A `MemoryWriterPort` exposes
   normalized execution events. Codex, Claude, and a future local process are
   adapters.
6. **Knowledge owns Markdown truth.** Index owns only projections.
7. **Jobs and work sessions are different services.** One is product execution
   state; the other is the user's remembered work.
8. **Transport transfers data; it never runs remote work.** SSH is an encrypted
   carrier, not an orchestration API.
9. **One central installation writes Markdown.** Remote collectors spool and
   export events, avoiding multi-writer Git and wiki conflicts in the first
   design.

This follows the current repo's strongest architecture lesson: services own
product verbs, stores own persistence, ports live by the service that owns the
contract, and integrations terminate external shapes.

## Host and environment identity

Do not use hostname or filesystem path as the stable id. Both change and may
leak personal or corporate information.

```python
Host(
    host_id="host_01K...",          # generated
    alias="laptop",                 # user-facing, editable
)

Environment(
    environment_id="env_01K...",
    host_id="host_01K...",
    kind="wsl",
    alias="wsl-ubuntu",
    parent_environment_id="env_windows_...",
)

Workspace(
    workspace_id="ws_01K...",
    environment_id="env_01K...",
    native_path="/home/user/my-service",
    project_ids=("proj_my_service",),
    git_remote_fingerprints=(...),
)
```

Absolute native paths remain private structured data. Durable pages cite a
workspace alias or artifact id, not an absolute path. Windows and WSL on the
same laptop are distinct environments under one host; an SSH Linux target is a
different host and environment. Container identity can later fit the same seam.

ActivityWatch offers useful prior art: it separates watchers from storage and
recommends a bucket per watcher and host, with a small event envelope of
timestamp, duration, and type-specific data [ActivityWatch data
model](https://docs.activitywatch.net/en/latest/buckets-and-events.html) and
[architecture](https://docs.activitywatch.net/en/latest/architecture.html).
Borrow the source/host separation, not its continuous desktop-monitoring scope
or schemaless payload as the entire domain model.

## Provenance and trust

There is no single global trust order for personal work:

- a Git commit is authoritative for what that commit contains;
- a command event is evidence that a collector observed an invocation and exit
  status, not that the command achieved its intended real-world effect;
- a transcript is authoritative for what was said, not whether an assistant's
  claim was true;
- a session is an interpretation of related evidence;
- a knowledge page is the maintained conclusion and may supersede an older
  interpretation.

W3C PROV's minimal concepts map well without adopting RDF:

- `Entity` -> artifact or knowledge revision;
- `Activity` -> work session or compile job;
- `Agent` -> person or software agent;
- `used`, `wasGeneratedBy`, and `wasDerivedFrom` -> evidence links.

The W3C model explicitly distinguishes entities, activities, and responsible
agents and uses these relationships to form provenance chains [W3C
PROV-O](https://www.w3.org/TR/prov-o/). Borrow the vocabulary and constraints,
not the ontology, triple store, or SPARQL machinery.

## Privacy and security contract

The personal product will hold more sensitive material than CodeAlmanac. Its
privacy model must be a product boundary, not documentation.

### Defaults

- Local-only; no product telemetry.
- Transcript bodies, command text, command output, file bodies, environment
  variables, and clipboard contents are **off by default**.
- Default transcript discovery stores safe metadata and a locator. Content is
  loaded only for an explicit compile/import scope.
- Shell collection, when added, defaults to cwd alias, start/end, duration,
  exit status, and Git context. Full command text is a separate opt-in. Output
  is never captured automatically.
- `.ssh`, credential stores, keychains, token files, environment dumps, and
  user-configured private paths are denied before read.
- Raw content has a visible retention period and explicit `export`, `purge`,
  and `forget` operations.
- Normal search and the viewer exclude raw content.
- Logs record ids, counts, and failure categories, not content payloads.

### Model-access policy

`local-first` does not mean a Codex or Claude call is local. Every compile job
must have a content-access class:

```text
metadata-only       no transcript/command/file bodies
selected-local      selected content may be read by a local runtime
selected-remote     selected content may be sent to the named remote runtime
```

Unattended jobs may not use `selected-remote` unless the user has opted in to
that content class and runtime explicitly. A run receipt should show which
events and artifacts were exposed, without duplicating their bodies into logs.

OpenTelemetry's security guidance is relevant beyond telemetry: minimize
collection, avoid sensitive data when possible, and use allowlisting,
filtering, deletion, or transformation at the collection boundary
[OpenTelemetry sensitive-data
guidance](https://opentelemetry.io/docs/security/handling-sensitive-data/).
Regex secret detection can be defense in depth, but it must not be the primary
contract.

### Storage claims

- Use platform-standard application data/config/cache directories rather than
  assuming `~/.workalmanac` has identical semantics everywhere.
- Set restrictive filesystem permissions where the platform supports them.
- Never promise encryption at rest until a reviewed OS-keyring-backed design is
  implemented. Full-disk encryption remains the user's responsibility in the
  MVP.
- If protected blobs are later added, use established OS cryptography and
  explicit key lifecycle; do not hand-roll encryption.
- Bundle/SSH transport must authenticate peers, checksum batches, be
  idempotent, and never transmit content classes outside policy.

ActivityWatch demonstrates the credible product posture: local usage data stays
on the user's device and is not transmitted to the developers
[ActivityWatch privacy policy](https://docs.activitywatch.net/en/latest/privacy.html).
Work Almanac should match that posture and be stricter about model egress.

## Event storage without full event sourcing

Use a narrow append-only observation ledger plus ordinary relational current
state. Do **not** make every product mutation an event-sourced aggregate.

Borrow:

- stable event ids and source sequence/dedupe keys;
- append-only accepted observations during retention;
- replayable session/index projections while evidence exists;
- materialized views for query performance.

Reject:

- reconstructing configuration, projects, privacy grants, and knowledge pages
  solely by replay;
- permanent immutability of sensitive data;
- compensating events as the only deletion mechanism;
- brokers, queues, snapshots, or upcasters before a concrete need.

Microsoft's current pattern guidance is unusually explicit that event sourcing
is complex, costly to migrate, and often inappropriate for MVPs, even while its
append-only audit trail and materialized views are valuable
[Event Sourcing pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing).
The privacy conflict is decisive here: raw personal data must be genuinely
deletable.

## Current subsystem judgment

| Current subsystem | Judgment | Work Almanac consequence |
| --- | --- | --- |
| `app.py` composition root | Keep shape, rewrite wiring | Good explicit dependency injection; current graph is repository-centric |
| `core/` typed models/errors/path helpers | Keep selectively | Rebrand and make path handling platform-aware |
| `repositories` | Redesign | Split logical `projects` from environment-bound `workspaces`; neither owns the vault |
| `sources` address/runtime service | Redesign | Split collectors, artifacts/evidence, and content access; stop using one overloaded noun |
| Codex/Claude transcript adapters | Keep as donors | Convert to collectors; remove exact-cwd affiliation and bounded prompt-rendering role |
| `sync` | Delete and replace | Observation import plus session correlation, not repo-grouped ingest |
| `wiki` Markdown parser/link/source model | Keep and simplify | Point at one private vault; retain Markdown links and evidence ids |
| topic DAG and topic mutation commands | Defer/delete from MVP | Start with folders plus simple tags |
| per-repository FTS index | Keep mechanisms, redesign scope | One disposable vault index covering knowledge and session summaries |
| `build` workflow | Delete | No "build one codebase wiki" lifecycle |
| `ingest` workflow | Replace with `compile memory` | Compile selected sessions/evidence into durable knowledge |
| `garden` workflow | Keep concept, redesign later | Vault-wide knowledge maintenance after the basic compile path proves useful |
| run ledger/events/attach/cancel | Keep useful mechanics, simplify | Generic compile jobs, no mandatory repository id or build/ingest/garden enum |
| detached global worker/process cancellation | Defer | Start foreground; restore only when actual long jobs require it |
| Yoke harness boundary | Keep as first runtime adapter | Storage and capture remain usable without Yoke; local runtime seam remains open |
| local viewer/search | Keep and redesign information architecture | Timeline, sessions, projects, decisions, unfinished work, evidence |
| launchd automation | Delete from product core | Manual MVP; later Windows Task Scheduler/systemd/launchd adapters behind one port |
| setup instruction installers | Reuse cautiously | Install agent-neutral Work Almanac guidance, not repo-local wiki doctrine |
| package updater | Defer | Not part of proving personal memory |
| anonymous PostHog telemetry | Delete | Incompatible with the private personal fork's simplest trustworthy posture |
| Git auto-commit prompt policy | Keep as optional vault policy | Git is useful for knowledge history; never assume a public remote |
| multi-wiki viewer/repository selector | Delete | One personal vault with project filters |
| Git/GitHub/web/filesystem source runtimes | Reuse selectively later | Artifacts are evidence, not first-class ingest address machinery in the walking slice |

## Incremental migration roadmap

The codebase has useful mechanisms, but a line-by-line rename would preserve
the wrong dependency graph. Use a temporary, explicitly bounded strangler
inside the fork: the new package does not call old product services, and the
old command remains only long enough to compare/import data. There is no
long-lived compatibility layer.

### Phase 0 — Freeze the contract and privacy threat model

Deliver:

- agreed nouns and four-layer contract;
- content classes and retention defaults;
- example fixtures for Codex, Claude, manual note, Git commit, Windows, WSL,
  and SSH-origin events;
- a deletion test proving selected raw content disappears;
- a decision on final product/package/CLI/vault names.

Exit criterion: a transcript, shell command, session, and decision can each be
classified unambiguously into the four layers.

### Phase 1 — Build the new walking skeleton

Create a new `workalmanac` package root rather than making current repository
parameters optional.

Deliver:

- platform-aware local state;
- vault, host, environment, project, and workspace models;
- intake with event dedupe and privacy filtering;
- manual `note` and structured JSON event import;
- explicit session create/attach/merge/split/close;
- private Markdown knowledge service;
- FTS over knowledge and session summaries;
- foreground CLI only.

Exit criterion: on one Windows machine, a user can record a note, attach it to a
session, create or edit a decision page, and retrieve both the session and
decision without an AI provider.

### Phase 2 — Convert existing transcript discovery into collectors

Use the current Codex and Claude JSONL readers as implementation donors.

Deliver:

- collector-owned cursors and source-event ids;
- metadata-only discovery by default;
- normalized agent turn/tool/result events when content is enabled;
- no exact-cwd-to-registered-repository requirement;
- workspace/project hints that sessionization may accept or ignore;
- raw retention and purge behavior.

Exit criterion: Codex and Claude activity from the same project can appear in
one user-correctable session, and an unrelated cwd is retained rather than
discarded as `unregistered-cwd`.

### Phase 3 — Add explicit memory compilation

Repurpose the normalized harness event concept and Yoke adapter behind a new
`MemoryWriterPort`.

Deliver:

- `compile session ... --using <runtime>`;
- content-access manifest and receipt;
- a writer constrained to the private vault;
- direct Markdown editing, validation, index refresh, and no-op support;
- provider-neutral agent instructions so an external/local agent can also read
  context and edit the vault without being embedded.

Exit criterion: the same selected session can be compiled by Codex or Claude;
the storage/session model contains no provider branch. A local model can use
the documented filesystem/CLI context contract even before a first-class local
runtime adapter is chosen.

### Phase 4 — Rebuild the viewer around personal work

Deliver:

- Today/recent sessions;
- project and environment filters;
- decisions, problems, procedures, systems, and unfinished views;
- evidence panel and source navigation;
- unified FTS with explicit layer labels;
- raw evidence hidden by default.

Exit criterion: the user's five core questions can be answered without opening
SQLite or a provider transcript directory.

### Phase 5 — Import existing CodeAlmanac knowledge

Do not make every old repo wiki a permanent child wiki.

Deliver:

- one-shot importer that copies useful pages under `projects/<project>/` or the
  appropriate durable neighborhood;
- new stable memory ids and evidence references;
- a report of pages skipped, copied, or requiring manual placement;
- preserved Git history by retaining the fork/archive, not by embedding old
  runtime schemas in the new product.

Exit criterion: current valuable `almanac/` content is searchable from the
personal vault and the new runtime has no dependency on the old registry.

### Phase 6 — Add cross-environment transport

Start with pull-based bundles, not a daemon.

Deliver:

- installation/collector identity and idempotent batches;
- filesystem import for Windows/WSL;
- SSH pull over the user's authenticated SSH;
- per-peer cursors, checksums, content-class enforcement, and offline spool;
- one central Markdown writer.

Exit criterion: work recorded on a Linux SSH host appears in the central
session ledger without copying forbidden content or allowing the bundle to
execute code.

### Phase 7 — Add opt-in shell and automation integrations

Only after real usage proves which signals matter:

- PowerShell and POSIX shell hooks with command text off by default;
- Git event enrichment;
- Task Scheduler, systemd timer, and launchd adapters if unattended collection
  is still valuable;
- a local model runtime adapter against one concrete, structured contract.

Exit criterion: every new collector passes privacy, dedupe, deletion, and
cross-platform fixture tests.

### Phase 8 — Cut over and delete the old product

Deliver:

- final command/package rename;
- removal of repository registration, per-repo init/build, repo-grouped sync,
  topic DAG machinery not adopted, launchd-only assumptions, telemetry, and old
  manuals/prompts;
- rewritten architecture tests enforcing the new dependency direction;
- no old-to-new runtime adapter left behind.

Exit criterion: a source scan finds no mandatory `repository_id` in event,
session, memory, job, or query roots, and the old package can be removed without
breaking the Work Almanac test suite.

## Rejected patterns

### "Make repository optional everywhere"

Rejected because repository ownership is embedded in run records, queue
selection, source inspection, sync grouping, index paths, viewer scope, and
workflow prompts. Optional fields would hide the wrong aggregate rather than
remove it.

### "One central wiki plus many existing repo wikis"

Rejected for the MVP because it leaves two sources of durable truth, requires
cross-wiki conflict rules, and keeps work with no repository homeless.

### "Write every event or transcript directly to Markdown"

Rejected because Git history makes deletion difficult, raw content is noisy and
sensitive, and activity records are not durable conclusions.

### "Summarize directly from transcript to final memory"

Rejected because it loses session boundaries, cross-tool evidence, user
correction, and provenance. The retained session layer is the necessary seam.

### "A single events table with arbitrary JSON is the entire domain"

Rejected because provider shapes would leak inward and every query would
reimplement semantics. Keep a typed envelope, typed safe attributes for known
event kinds, and an opaque protected-content reference only at the edge.

### Full event sourcing/CQRS

Rejected because privacy deletion, schema evolution, compensating events, and
replay machinery cost more than this personal product needs. Use ordinary
relational state plus an append-oriented observation ledger and disposable
read projections.

### Timestamp-only sessionization

Rejected because work overlaps, machines drift, SSH resumes, and provider
sessions can continue after long pauses. Correlation is multi-signal and
user-correctable.

### Always-on central daemon first

Rejected because Windows/WSL/Linux/SSH service management and security would
consume the MVP before useful memory exists. Foreground import and later
pull-based bundles prove the model with less machinery.

### Automatic full shell history and output capture

Rejected because it maximizes credential, token, customer-data, and personal
data exposure. Metadata-first plus explicit command/content opt-in is safer.

### "Local-first" as permission to send content to any configured model

Rejected because Codex and Claude may be remote services. Local storage and
model egress are independent policies.

### One adapter per local LLM immediately

Rejected as speculative machinery. Define one runtime port and an
agent-neutral CLI/filesystem contract; add a concrete local adapter when the
actual runtime (Ollama, llama.cpp, LM Studio, a custom server, etc.) is chosen.

### Vector search first

Rejected until FTS5 fails on recorded queries. Personal work has strong lexical
anchors—project names, commands, errors, commits, hosts, and decision language.

## Decisions still required before implementation

1. Final public name, package, CLI, state directory, and vault directory.
2. Whether the first vault is a user-selected private Git repository or a
   normal directory with optional Git initialization.
3. Raw-event and protected-content retention defaults.
4. Whether absolute paths may be stored in private state by default or require
   explicit opt-in.
5. Which compile runtime is the first supported writer and which content access
   it receives.
6. Whether manual session boundaries (`start`/`stop`) are part of the MVP or
   only correction verbs are required.
7. Which machine is the single Markdown writer when cross-host transport lands.

These decisions affect product trust and storage shape. They should not be
hidden in setup defaults.

## Files and sources inspected

Repository doctrine and active agreements:

- `AGENTS.md`
- `CLAUDE.md`
- `MANUAL.md`
- `README.md`
- `notes.md`
- `implementation-tickets.md`
- `docs/python-port-live-agreement.md`
- `docs/refactor-audit-2026-07-27/README.md`
- `docs/refactor-audit-2026-07-27/source-map.md`
- `docs/refactor-audit-2026-07-27/subagent-briefs.md`
- `docs/refactor-audit-2026-07-27/worklog.md`
- `docs/refactor-audit-2026-07-27/reports/boundary-critic.md`
- `docs/refactor-audit-2026-07-27/reports/feature-skeptic.md`
- `docs/refactor-audit-2026-06-09/reports/target-architect.md`
- `docs/refactor-audit-2026-06-09/target-architecture.md`
- `docs/architecture-audit-2026-06-08/target-architecture.md`
- the user-provided pasted design discussion under the Codex attachment store

Current composition and domain boundaries:

- `pyproject.toml`
- `src/codealmanac/app.py`
- `src/codealmanac/settings.py`
- `src/codealmanac/services/repositories/models.py`
- `src/codealmanac/services/repositories/tables.py`
- `src/codealmanac/services/sources/models.py`
- `src/codealmanac/services/sources/ports.py`
- `src/codealmanac/services/sources/service.py`
- `src/codealmanac/services/sources/transcripts.py`
- `src/codealmanac/services/runs/models.py`
- `src/codealmanac/services/runs/tables.py`
- `src/codealmanac/services/wiki/models.py`
- `src/codealmanac/services/index/models.py`
- `src/codealmanac/services/index/schema.py`
- `src/codealmanac/integrations/sources/transcripts/models.py`
- `src/codealmanac/integrations/sources/transcripts/claude.py`
- `src/codealmanac/integrations/sources/transcripts/codex.py`
- `src/codealmanac/integrations/sources/transcripts/runtime.py`
- `src/codealmanac/workflows/sync/service.py`
- `src/codealmanac/workflows/sync/models.py`
- `src/codealmanac/workflows/sync/evaluation.py`
- `src/codealmanac/workflows/sync/queue.py`
- `src/codealmanac/workflows/ingest/service.py`
- `src/codealmanac/workflows/operations/service.py`
- `src/codealmanac/workflows/run_queue/specs.py`
- launchd, repository, run, index, viewer, and topic references found through
  focused source searches

Current Almanac explanations:

- `almanac/architecture/service-boundaries.md`
- `almanac/architecture/sources/source-resolution-and-runtime.md`
- `almanac/architecture/lifecycle/run-queue-and-sync.md`
- `almanac/concepts/source-material.md`
- `almanac/concepts/run-ledger.md`
- `almanac/decisions/local-only-python-product.md`

External primary/official prior art:

- [ActivityWatch architecture](https://docs.activitywatch.net/en/latest/architecture.html)
- [ActivityWatch data model](https://docs.activitywatch.net/en/latest/buckets-and-events.html)
- [ActivityWatch privacy policy](https://docs.activitywatch.net/en/latest/privacy.html)
- [OpenTelemetry Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/)
- [OpenTelemetry handling sensitive data](https://opentelemetry.io/docs/security/handling-sensitive-data/)
- [W3C PROV-O](https://www.w3.org/TR/prov-o/)
- [SQLite FTS5](https://www.sqlite.org/fts5.html)
- [Microsoft Event Sourcing pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
