# Target Architecture

## Product sentence

Work Almanac is a local-first personal memory that collects bounded evidence
from the tools and environments a person works in, groups that evidence into
work sessions, and uses a chosen curator agent to maintain a searchable
Markdown knowledge base.

The person is the center. Repositories, hosts, agents, and shells are context.

## Architectural decision

This should be an intentional product fork, not a compatibility mode inside
CodeAlmanac.

- Preserve Git history and reusable implementation.
- Rename the product, package, command, state directory, and domain nouns early.
- Do not support CodeAlmanac and Work Almanac behavior in one runtime.
- Do not carry old CLI compatibility aliases.

The existing dependency direction remains useful:

```text
cli/server
  -> app
    -> workflows
      -> services
        -> stores/ports
          -> integrations
```

The services and workflows inside it change.

## Information architecture

The durable artifact is one private vault:

```text
work-almanac/
|-- README.md
|-- inbox/
|-- projects/
|   |-- work-almanac.md
|   `-- my-service.md
|-- decisions/
|   `-- central-vault-is-single-writer.md
|-- problems/
|   `-- payment-timeout.md
|-- procedures/
|   `-- restore-dev-server.md
|-- systems/
|   |-- windows-laptop.md
|   `-- dev-server-01.md
`-- unfinished/
    `-- work-almanac-capture-mvp.md
```

These folders are durable reading shapes, not intake queues. Raw transcripts,
shell history, cursor state, secrets, and scheduler logs do not belong in Git.
Start with folders and flat tags, not the current topic DAG. Treat daily
activity as a session query or generated export until real use proves that
permanent daily Markdown pages are valuable.

## Four distinct data layers

### 1. Source material

Provider-owned records remain where they were created whenever possible:
Codex JSONL, Claude JSONL, Git, terminal wrapper results, SSH-side records, and
manual notes.

Source material is evidence, not the Work Almanac database.

### 2. Capture ledger

The private capture ledger stores normalized, redacted, idempotent events and
source cursors. Event content is retention-bound and genuinely deletable. The
ledger is not committed to the Markdown vault.

```python
class CaptureEvent:
    event_id: EventId
    schema_version: int
    occurred_at: datetime | None
    observed_at: datetime
    kind: EventKind
    origin: CaptureOrigin
    session_hint: SessionHint | None
    workspace: WorkspaceHint | None
    project_hints: tuple[ProjectHint, ...]
    source: SourceLocator
    attributes: SafeAttributes
    content: ProtectedContentRef | None
    sensitivity: Sensitivity
    fingerprint: str
```

`CaptureOrigin` includes:

- stable node id;
- host label;
- environment (`windows-powershell`, `wsl-ubuntu`, `ssh-linux`, etc.);
- collector kind and version;
- originating agent/tool when known.

The ledger gives every collector its own cursor. A global
`last_completed_at` watermark is insufficient.

### 3. Work sessions

Sessions are retained, user-correctable interpretations of related work. They
do not make a repository mandatory and are not identical to provider
conversations or curator jobs:

```python
class WorkSession:
    session_id: SessionId
    title: str | None
    goal: str | None
    outcome: str | None
    started_at: datetime
    ended_at: datetime | None
    origin_ids: tuple[OriginId, ...]
    event_ids: tuple[EventId, ...]
    project_ids: tuple[ProjectId, ...]
    status: SessionStatus
    continuation_of: SessionId | None
    grouping_basis: GroupingBasis
    user_confirmed: bool
```

Prefer explicit provider session ids, shell-session ids, run ids, and causal
links. Use a deterministic time-gap heuristic only as a fallback. Users can
merge, split, reassign, and close sessions without rewriting raw evidence.
Accepted session facts survive raw-content expiry. AI may interpret the
session but should not own event identity or deduplication.

### 4. Durable memory

Markdown pages contain only knowledge worth retrieving later: decisions,
project state, solved problems, procedures, system context, and unfinished
work. Pages cite capture evidence:

```yaml
sources:
  - id: timeout-session
    type: session
    session: session_01J...
  - id: fix-commit
    type: commit
    commit: a83f92c
```

The index is disposable and rebuilt from Markdown plus retained session
summaries. Normal search and the viewer exclude raw evidence. The ledger,
sessions, Markdown, and index have different authority, retention, privacy, and
synchronization rules and must not share one accidental schema.

## Main flow wireframe

```python
# Deterministic intake: no AI and no Markdown writes.
batch = capture.collect(source, cursor=ledger.cursor_for(source))
events = capture.normalize(batch, origin=node.identity())
events = privacy.filter(events, policy=config.capture_policy)
receipt = ledger.append(events)                 # idempotent by event_id
sessions.refresh(receipt.accepted_event_ids)

# User correction remains first-class.
sessions.merge(primary, continuation)
sessions.assign_project(session_id, project_id)
sessions.close(session_id, outcome="tests pass")

# Judgment: the chosen curator writes durable knowledge directly.
selection = distill.select_sessions(status="ready", since=last_distill)
request = DistillRequest(
    vault=vault.id,
    sessions=selection,
    content_access="selected-remote",
)
receipt = curator.run(request, vault, ledger.evidence_reader())
vault.validate()
index.refresh(vault)

# Maintenance remains independent from new intake.
garden.run(vault, index.health())
```

There is no proposal JSON, approve/apply state machine, or generic processing
pipeline. Deterministic intake owns identity, privacy, and replay safety. The
curator prompt owns judgment and prose. Start curator work in the foreground;
restore detached jobs, cancellation, and attachable logs when actual run
duration makes them necessary.

## Provider axes

Two provider axes must remain separate.

### Capture providers

These describe where work evidence comes from:

- Codex transcript collector;
- Claude transcript collector;
- local-model transcript/import collector;
- Git activity collector;
- manual note collector;
- explicit shell command wrapper;
- SSH-side collector.

### Curator providers

These describe which agent may edit the durable vault:

- Codex;
- Claude;
- one concrete local-model runner later.

Supporting a local model as an input does not require trusting it as the
curator. Supporting it as a curator requires a real tool-capable adapter and
quality/safety proof, not merely an OpenAI-compatible chat endpoint.

## Privacy and model-access contract

Privacy filtering runs before persistence and before any model call.

- Local-only by default; no product telemetry.
- Transcript bodies, command text/output, file bodies, environment variables,
  and clipboard content are off by default.
- Metadata may include a private content locator; bodies are loaded only for an
  explicit import or distill scope.
- Raw content has visible retention plus `purge` and `forget` operations.
- Credential stores, SSH keys, token files, environment dumps, and configured
  private paths are denied before read.
- Logs contain ids, counts, and failure categories, not copied content.

Every curator request declares one content-access class:

```text
metadata-only       no transcript, command, output, or file bodies
selected-local      selected content may be read by a local runtime
selected-remote     selected content may be sent to the named remote runtime
```

Unattended work cannot use `selected-remote` without an explicit standing grant.
A run receipt records which evidence ids were exposed without duplicating their
bodies.

## Multi-host topology

### Target: one writer, many collectors

```text
Windows collector ----\
WSL collector ----------> private vault host -> capture ledger -> curator
Linux/SSH collector ----/                         |
                                                  v
                                         Git-tracked Markdown vault
```

The canonical vault host may initially be the user's Windows laptop and later a
private Linux server. Only the vault host runs distill/garden and writes
Markdown. This avoids cross-host SQLite corruption and Git merge conflicts from
multiple curator writers.

Collectors append idempotent capture batches. The future transport may use SSH,
but the first MVP should prove local collection before building remote
transport machinery.

## Target service map

```text
services/
  vault/        Markdown root, validation, Git mutation boundary
  capture/      event contracts, cursors, dedupe
  privacy/      collection, content-access, retention policy
  sessions/     correlation, correction, retained session state
  projects/     optional project identities and aliases
  memory/       page/source/link/topic read models
  index/        derived FTS and backlinks
  runs/         curator job ledger and cancellation
  curators/     normalized agent-runner port
  nodes/        host/environment identity
  automation/   task definitions independent of OS scheduler

workflows/
  collect/      collectors -> normalized ledger
  distill/      sessions -> durable Markdown
  garden/       durable knowledge maintenance
  transport/    deferred cross-node batch transfer

integrations/
  capture/
    codex/
    claude/
    git/
    manual/
    shell/      deferred until explicit wrapper UX is agreed
  curators/
    yoke/
    local/      deferred until a concrete runner exists
  schedulers/
    windows/
    systemd/
    launchd/
  transport/
    ssh/        deferred until local capture is proven
```

Do not create empty packages in advance. This map names the intended seams;
implementation should appear slice by slice.

## Minimal CLI

```text
wa init <vault-path>
wa note <text>
wa collect [--from codex,claude,git]
wa inbox
wa session [show|merge|split|assign|close]
wa distill [--since <duration> | --session <id>]
wa search [query]
wa show <page>
wa ask <question>
wa garden
wa status
wa serve
wa jobs [show|logs|attach|cancel]
wa privacy
wa purge
wa forget
```

Reserve `sync` for future node-to-vault transport. Do not continue using it to
mean "scan transcript files."

## Patterns adopted

### Ports and adapters

Collectors, curator providers, schedulers, and transport terminate at
service-owned typed contracts.

### Functional core, imperative shell

Event identity, redaction decisions, cursor advancement, deduplication, and
session correlation are deterministic functions. Filesystem, SQLite, Git,
processes, and provider calls remain at the edge.

### Command/query separation

Collection/distillation/gardening mutate state. Search/show/status/ask read
through dedicated projections. `ask` may retrieve recent evidence but does not
silently modify durable memory.

### Single-writer hub

Many nodes collect; one vault authority writes the capture ledger and Markdown.
This is simpler and safer than distributed SQLite or multi-writer Markdown
merges.

## Patterns rejected

- **Full event sourcing:** capture events are evidence, not the sole source of
  truth for rebuilding every product state.
- **Generic plugin framework:** typed adapter seams are enough until a second
  independently shipped extension exists.
- **Semantic/vector search in the first slice:** preserve FTS5 and add hybrid
  retrieval only after measured misses.
- **Raw shell/key/window surveillance:** collect explicit work evidence, not
  everything a person does.
- **Cloud account/service:** a private local or SSH-reachable hub is sufficient
  for the requested use case.
- **Multiple curator writers:** this creates avoidable Git and page-merge
  conflicts.
