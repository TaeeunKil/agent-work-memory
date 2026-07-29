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

The Windows Codex adapter applies the same bounded sharing-violation retry
while reading its structured handoff. Each retry repairs the Vault ACL again
before reading, covering sandbox helper handles that briefly outlive the main
Codex process.

Bounded failure messages include only a lifecycle stage name and exception
class, preserving path redaction while making provider, handoff-read, and
handoff-apply failures distinguishable.

The hidden Windows Codex CLI bridge runs its buffered child process in a worker
thread and parses the completed JSONL output afterward. The curator UI does not
stream provider output, so avoiding Windows asyncio subprocess transports
removes Proactor `Event loop is closed` and closed-pipe `ValueError` failures
without changing visible behavior.

## Invariants

- Cleanup runs after every successful or failed curator attempt.
- A transient directory lock is retried without opening a console window.
- A transient handoff read lock is repaired and retried before parsing JSON.
- A persistent Windows sharing lock can leave a disposable directory for a
  later cleanup pass, but cannot turn a curator result into a failed receipt.
- Non-Windows cleanup keeps the same direct `rmtree` behavior.

## Verification

- Unit test proves cleanup repairs permissions and retries a transient lock.
- Full pytest, Ruff, and viewer JavaScript gates.
- Retry the pending session through `awm auto-distill run`.
