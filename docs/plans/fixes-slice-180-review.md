# Slice 180 review fixes

## Review result

No findings.

The change keeps the standing grant finite and expiring, changes only the
service-owned validation boundary, and leaves the conservative default and
per-run cap unchanged. Tests cover both the requested 439-session backlog and
the new upper boundary. The remaining operational risk is curator runtime:
slow or failed runs can extend the time needed to drain the backlog, while the
scheduler's single-instance policy prevents overlapping workers.

