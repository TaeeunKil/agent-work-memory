# Work Almanac Distill Slice

## Goal

Promote selected retained agent sessions into durable, maintained Markdown Wiki
knowledge without coupling storage to Codex, Claude, or any future local model.

This slice turns:

```text
inbox/agent-sessions/*
```

into careful updates under:

```text
projects/
decisions/
problems/
procedures/
systems/
unfinished/
```

The session record remains evidence. Distillation does not rewrite or delete
the record.

## Call shape

```python
result = app.distill.run(
    DistillSessions(
        session_ids=("ses_...",),
        runtime="codex",
        model=None,
        content_access=ContentAccess.SELECTED_REMOTE,
    )
)
```

## Boundaries

- `SessionsService` owns selected evidence and distilled state.
- `CuratorsService` owns a provider-neutral runtime port.
- `YokeCuratorAdapter` is the first Codex/Claude implementation.
- `VaultService` owns snapshots, allowed mutation paths, rollback, and Markdown
  validation.
- `DistillSessionsWorkflow` owns orchestration and receipts.
- `SearchService` refreshes only after a valid successful run.

## Content access

Every run declares one class:

- `metadata-only`: session metadata only;
- `selected-local`: selected event bodies may be read by a local runtime;
- `selected-remote`: selected event bodies may be sent to the named remote
  runtime.

The bundled Yoke Codex/Claude adapters reject `selected-local`. The CLI requires
an explicit `--allow-remote-content` switch before it selects
`selected-remote`.

Receipts store session ids, runtime, model, content-access class, status, and
changed Wiki paths. They never duplicate event bodies.

## Mutation contract

The curator:

- runs with the Vault as its working directory;
- receives read/write tools but no shell, network, or helper-agent tools;
- may change only Markdown under durable Wiki directories;
- may no-op when the evidence adds no durable knowledge;
- never edits `inbox/agent-sessions/`;
- never commits or pushes Git changes.

The workflow copies only durable Wiki material into an isolated disposable
workspace before execution. `.git` and the complete `inbox/` are excluded, so
the curator cannot bypass content-access policy by opening a session page.
Failed runs and forbidden changes are discarded with that workspace. Only
validated durable Markdown changes are atomically copied back to the real
Vault.

## Verification

- fake curator creates and updates one durable page;
- same session can no-op safely;
- selected content appears only under the matching access class;
- forbidden inbox edits are rolled back;
- failed runs are rolled back;
- successful runs mark sessions distilled and record a body-free receipt;
- CLI request mapping is covered without invoking a paid provider;
- Yoke readiness and request projection are unit-tested at the adapter edge.

## Deferred

- detached/background jobs;
- automatic scheduled distillation;
- concurrent curator runs;
- local-model runtime implementation;
- semantic retrieval;
- automatic Git commits;
- viewer presentation of receipts.
