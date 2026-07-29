# Slice 162 — Cursor transcript collection

## Intent

Collect Cursor Composer sessions alongside Codex and Claude so work performed
in Cursor can enter the same private session evidence and Wiki-distillation
pipeline.

Cursor-hosted Codex and Claude extensions remain owned by their native
collectors when they write the standard `.codex` or `.claude` stores. The
Cursor provider owns only Cursor Composer's SQLite store.

## Shape

```text
CursorTranscriptCollector.discover(home)
  -> locate Cursor/User/globalStorage/state.vscdb
  -> snapshot the live SQLite database in memory
  -> normalize composerHeaders into discovered sessions

CursorTranscriptCollector.read(session)
  -> snapshot the database again
  -> read bubbleId:<composer>:* records
  -> normalize stable user/assistant text bubbles into AgentEvent
  -> let the existing collection, Vault, search, and distill pipeline proceed
```

The SQLite and JSON formats stay inside the Cursor integration. Workspace URIs
are normalized at that boundary into stable path identities for local, WSL,
and SSH-backed workspaces.

## Scope

- Add `cursor` as a local transcript provider and default local collection
  choice.
- Preserve Cursor's conversation title, workspace, and timestamps.
- Capture non-empty user and assistant messages.
- Read a consistent in-memory snapshot so a running Cursor process can keep
  writing safely.
- Cover Windows, macOS, and Linux Cursor storage locations.
- Keep SSH remote registration limited to Codex and Claude stores; Cursor's
  remote workspace conversations are already represented in the local Cursor
  database.

## Verification

- Synthetic SQLite tests for discovery, content collection, incrementality,
  and file/WSL/SSH workspace URI normalization.
- Existing AWM pytest, Ruff, and viewer JavaScript gates.
