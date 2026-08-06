# Slice 189: Bound and normalize Codex session records

## Intent

Keep retained Codex evidence useful and publishable when a long-lived thread
contains modern Codex response items, internal telemetry, large tool results,
or moves from the live session store into `archived_sessions`.

The current collector expects an older nested `payload.item` shape. Modern
records put response-item fields directly in `payload`, so AWM falls back to
serializing complete transport envelopes. A real 35,609-event thread therefore
produced a 98 MB Markdown page from a 622 MB JSONL source. Per-event truncation
did not provide a session-level bound.

## Shape

```text
CodexTranscriptCollector.discover(home)
  -> scan live sessions and archived_sessions
  -> preserve one AWM session identity across a physical path move
  -> mark archived records complete

CollectAgentRecordsWorkflow.collect(...)
  -> compare collector normalizer_version with the retained cursor
  -> append when the version and source continuity match
  -> replace the session event projection when normalization changes

normalize_codex(record)
  -> parse direct response_item payloads into message/tool events
  -> omit encrypted reasoning and operational telemetry
  -> retain a small bounded fallback only for unknown evidence-bearing shapes

bundle = session_records.render(session, events)
vault.replace_session_record(bundle)
  -> keep the canonical session page as the stable citation target
  -> render small records in that page
  -> render large records into deterministic part-001..N pages
  -> remove obsolete generated parts after a successful replacement

vault_repository.push(...)
  -> reject a remaining oversized file before Git staging
```

## Boundaries

- SQLite remains the private evidence store; Markdown is a readable projection.
- User and assistant messages, tool calls, and bounded tool results are evidence.
- Token counters, encrypted reasoning, turn context, world state, and repeated
  thread settings are transport telemetry and do not belong in the Wiki.
- The canonical `inbox/agent-sessions/<provider>-<session-id>.md` path remains
  stable so durable-page citations and Viewer navigation do not break.
- Parts split only at event boundaries. A single oversized event is divided
  into explicit continuation fragments without losing text.
- A normalizer-version replay is atomic at the database boundary: old projected
  events do not survive beside their normalized replacements.
- Source relocation may reuse an existing session only when provider identity
  matches and the previous physical source no longer exists.
- Git file-size validation is fixed product policy, not curator judgment.

## Verification

- Modern direct Codex messages and function/custom-tool calls normalize into
  typed events without raw JSON envelopes.
- Codex telemetry and encrypted reasoning are omitted.
- Nearby duplicate message representations collapse without merging legitimate
  repeated messages from separate turns.
- A normalizer-version change replays and replaces prior events.
- Moving a Codex JSONL file into `archived_sessions` preserves the AWM session
  id, source citations, and event history while marking the session complete.
- Large session records keep a stable canonical page and produce deterministic,
  size-bounded numbered parts; rerendering cleans up stale parts.
- Vault Git publication refuses any file above the fixed safety threshold.
- Existing AWM tests, Ruff, JavaScript syntax, and architecture checks pass.
