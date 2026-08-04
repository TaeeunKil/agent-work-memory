# Fixes - Slice 186 review

## Findings

### Curator deletion should reach the canonical validation error

Frontmatter preservation initially attempted to read every changed existing
path. A curator deletion would therefore raise `FileNotFoundError` before the
Vault validator could report the product invariant that durable pages may not
be deleted.

**Fix:** skip absent targets during preservation and leave deletion handling to
`validate_distill_changes`. An isolated test covers the resulting error.

### Scheduled exit handling should be explicit

The scheduled wrapper initially caught `BaseException` to close ordinary gaps
left by `KeyboardInterrupt` or `SystemExit`. That scope also included process
control exceptions that should not be normalized by application code.

**Fix:** catch `Exception`, `KeyboardInterrupt`, and `SystemExit` explicitly.
Hard process termination remains recoverable through Activity PID
reconciliation on the next viewer read or scheduled Activity start.

## Review result

No further findings. The process-liveness decision is behind a service-owned
port, OS inspection stays in the integration layer, existing metadata repair
stays inside the disposable curator workspace, and strict validation remains
the only gate to the real Vault.
