# Slice 164 — Windows curator workspace cleanup

## Intent

Keep a transient Windows directory lock from masking the curator's real result
or leaving automatic Wiki distillation stuck on a generic `PermissionError`.

## Shape

The Vault creates its disposable curator directory with `mkdtemp`, then owns
cleanup explicitly:

1. restore the parent account's ACL across the complete temporary tree;
2. remove the tree;
3. retry short-lived access-denied and sharing-violation failures (`WinError`
   5 and 32) for a bounded interval;
4. defer a still-locked disposable directory instead of replacing the
   curator's durable result or original error with a cleanup error.

## Invariants

- Cleanup runs after every successful or failed curator attempt.
- A transient directory lock is retried without opening a console window.
- A persistent Windows sharing lock can leave a disposable directory for a
  later cleanup pass, but cannot turn a curator result into a failed receipt.
- Non-Windows cleanup keeps the same direct `rmtree` behavior.

## Verification

- Unit test proves cleanup repairs permissions and retries a transient lock.
- Full pytest, Ruff, and viewer JavaScript gates.
- Retry the pending session through `awm auto-distill run`.
