# Slice 163 — Windows curator handoff permissions

## Intent

Keep automatic Wiki distillation retryable when the Windows Codex sandbox
changes ACL ownership on `.awm-curator-output.json`.

## Shape

```text
YokeCuratorAdapter.run(request)
  -> parent creates an empty handoff file
  -> Codex writes the structured handoff
  -> injected workspace_permission_repair(request.vault_path)
  -> parent reads and applies the handoff
  -> disposable workspace can be removed
```

The composition root supplies the Vault-owned permission repair operation.
Yoke knows only that its Windows handoff must be parent-readable before it
interprets the structured result.

## Invariants

- Repair runs after the provider process stops and before handoff reading.
- Repair also runs when the provider reports failure so cleanup is not masked
  by a secondary `PermissionError`.
- Non-Windows and non-Codex curator paths remain unchanged.
- Errors exposed through receipts stay bounded and path-free.

## Verification

- Adapter test proves repair occurs between provider completion and handoff
  parsing.
- Full AWM pytest, Ruff, and viewer JavaScript gates.
- Retry the previously requeued session through `awm auto-distill run`.
