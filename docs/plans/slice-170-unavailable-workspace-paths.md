# Slice 170 — Unavailable workspace paths

## Intent

Keep transcript collection and distillation available when a retained agent
session names a workspace that Windows cannot currently resolve, such as a
stopped WSL distribution or disconnected network share.

## Architectural fit

Workspace identity is a sessions-domain concern. A single normalization
function in `services.sessions.distillation` owns the best-effort conversion:

```python
workspace = normalized_workspace_path(recorded_path)
```

It prefers filesystem-aware resolution, then falls back to lexical absolute
normalization when the recorded location is unavailable. Collection filtering
and same-workspace grouping both consume that boundary.

## Safety

- Do not probe, mount, reconnect, or modify the unavailable workspace.
- Preserve internal AWM workspace exclusion by checking normalized path parts.
- Do not skip otherwise valid historical sessions merely because their former
  workspace is offline.

## Acceptance

- Codex collection succeeds when a transcript records an unavailable workspace.
- Internal workspace filtering continues to use the same normalized boundary.
- Workspace comparison cannot fail solely because a recorded path is offline.
