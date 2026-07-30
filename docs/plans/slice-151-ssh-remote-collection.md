# Slice 151: read-only SSH agent-record collection

## Outcome

Agent Work Memory can register explicit SSH hosts, copy only changed Codex and
Claude transcript files into private local state, and feed those snapshots
through the existing session, cursor, Vault, Wiki, and search path.

The existing five-minute `wa sync` automatically includes registered remote
hosts. A remote host is never modified.

## Architectural fit

The current collector contract already accepts a home-shaped directory:

```python
snapshot = app.remotes.snapshot(host)
receipt = app.collect.collect(
    CollectAgentRecords(
        home=snapshot.local_home,
        providers=host.providers,
        include_content=request.include_content,
    )
)
```

The new axis is remote materialization, not transcript interpretation.
Therefore:

- `services/remotes/` owns registered-host models, status, persistence, and
  product verbs;
- `services/remotes/ports.py` owns the read-only snapshot adapter contract;
- `integrations/remotes/ssh.py` implements that contract with OpenSSH;
- `workflows/remote_sync/` coordinates snapshots with the existing collection
  workflow;
- `workflows/sync/` aggregates local and remote collection receipts behind the
  existing single-instance lock.

This follows the local architecture rule that services own product verbs,
stores own persistence, and integrations implement service-owned ports. It
also keeps the CLI as an adapter. See
`docs/reference/cosmic-python/chapter_04_service_layer.md` and
`docs/reference/cosmic-python/chapter_13_dependency_injection.md`.

## CLI contract

```powershell
wa remote add <ssh-host> [--from codex] [--from claude]
wa remote list
wa remote status <ssh-host>
wa remote sync [<ssh-host>] [--include-content]
wa remote remove <ssh-host>
```

`ssh-host` is a concrete OpenSSH host/config alias, optionally including
`user@`. Port, key, proxy, and jump-host policy remain in the user's SSH
configuration.

## Read-only SSH protocol

1. Run OpenSSH in `BatchMode=yes` with bounded connection time.
2. Run a standard-library Python helper remotely to enumerate regular,
   non-symlink `*.jsonl` files below:
   - `~/.codex/sessions`
   - `~/.claude/projects`
3. Compare the typed remote manifest with the last private local snapshot.
4. Request changed files in one ZIP stream.
5. Validate every archive path, file count, compressed size, and expanded
   size before writing beneath the host's private cache.
6. Feed the cache into the existing collectors.

The helper only reads files and writes protocol bytes to stdout. It never
creates remote files, changes permissions, installs packages, or executes an
agent.

OpenSSH password/passphrase prompts are disabled for scheduled runs. A user
must establish host trust and working key/agent authentication with ordinary
`ssh <host>` first.

## Privacy and safety

- Remote transcript bodies are retained only when `--include-content` is
  enabled in the invoking sync settings.
- Host targets reject whitespace, shell metacharacters, option-like prefixes,
  and wildcard SSH aliases.
- Raw SSH stderr, remote paths, keys, and transcript contents never enter
  status records or normal CLI errors.
- Remote cache lives under the existing private Agent Work Memory state directory.
- Archives are treated as untrusted and every member is containment-checked
  before extraction.
- A failed host does not prevent successful local collection or other remote
  hosts; its bounded status remains visible through `wa remote list/status`.

## Durable-Wiki clarification

Automatic sync retains evidence and refreshes search. It still does not invoke
an LLM or write curated prose.

Diagnostics will explicitly report:

- retained session count;
- durable Wiki page count;
- sessions waiting for distillation;
- the command needed to run selected distillation.

Automatic remote or paid-model distillation remains out of scope until the
owner selects a runtime and explicit content policy.

## Files

- `src/agentworkmemory/services/remotes/`
- `src/agentworkmemory/integrations/remotes/`
- `src/agentworkmemory/workflows/remote_sync/`
- `src/agentworkmemory/app.py`
- `src/agentworkmemory/cli.py`
- `src/agentworkmemory/workflows/sync/`
- `src/agentworkmemory/services/diagnostics/`
- `tests/test_agentworkmemory_remotes.py`
- Agent Work Memory user/completion plans

## Verification

- Service tests with an in-memory fake SSH snapshot adapter.
- Adapter tests with a fake `ssh` executable/protocol process.
- Archive traversal, symlink, size, invalid-host, unavailable-host, and
  idempotency tests.
- Local + multiple-remote aggregation under the existing sync lock.
- CLI mapping and bounded output tests.
- Scheduler command contract remains unchanged and automatically includes
  registered remotes.
- Agent Work Memory regression suite, Ruff, package build, editable reinstall.
- Real `wa remote list`; real host registration only after a concrete host is
  chosen from the user's SSH configuration.

## Out of scope

- Discovering or connecting to every host in `~/.ssh/config` automatically.
- Password storage or interactive authentication.
- Windows remote-host transcript layouts.
- Remote installation of Agent Work Memory.
- Shell-history or arbitrary filesystem collection.
- Automatic paid/remote distillation.
