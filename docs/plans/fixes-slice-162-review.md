# Slice 162 review fixes

## Findings addressed

### Cursor database was snapshotted once per conversation

The first implementation reopened and copied the complete live SQLite database
for every Cursor session. A single collection now builds one typed bubble index
from one snapshot and shares it across all discovered Composer sessions.

### Structured Cursor workspace URIs were rejected

Current Cursor records may encode `workspaceIdentifier.uri` as a structured URI
object rather than a string. A typed `CursorUri` edge model now accepts both
forms and normalizes its external URI. Real-store verification increased
discovery from 217 partial headers to all 410 headers, including 193 workspace
identities.

### Cursor was accidentally offered as an SSH snapshot provider

Local and SSH-remote provider choices now have separate named tuples. Cursor is
available for local collection, while SSH snapshot registration remains
limited to the remote `.codex` and `.claude` stores it actually supports.

## Residual format boundary

The collector intentionally retains non-empty user and assistant text bubbles.
Cursor's empty capability/tool-state bubbles are not durable conversational
evidence and are not copied into AWM. Unknown or future JSON shapes are skipped
at the provider edge without leaking raw Cursor payloads downstream.
