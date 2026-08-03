# Slice 172 — Current Cursor agent transcripts

## Intent

Collect current Cursor Agent conversations from Cursor's durable JSONL
transcripts while retaining the existing SQLite Composer reader for older
history. Do not register blank Composer headers as retained work sessions.

## Shape

`CursorTranscriptCollector` owns both Cursor storage layouts:

```text
CursorTranscriptCollector.discover(home)
  -> read SQLite Composer headers and bubble identities
  -> scan ~/.cursor/projects/*/agent-transcripts/*/*.jsonl
  -> prefer a non-empty legacy conversation when both layouts contain it
  -> use JSONL when it is the only durable conversation body
  -> exclude headers with neither source

CursorTranscriptCollector.read(session)
  -> read JSONL user/assistant text records when selected
  -> otherwise read legacy SQLite text bubbles
  -> return the existing provider-neutral AgentEvent contract
```

The discovered session keeps a stable provider source identity separate from
an optional content path. This lets a provider catalog or database identify a
session while a transcript file supplies its body, without leaking Cursor
storage details into collection workflows or session services.

## Invariants

- Current main-agent JSONL transcripts enter the ordinary session, Vault,
  search, and distillation pipeline.
- Cursor subagent JSONL files are not promoted as separate user work sessions.
- A Composer header with no legacy bubble records and no JSONL transcript is
  not discovered.
- Legacy SQLite conversations continue to collect incrementally.
- When both sources exist, the established legacy source remains selected so
  existing sessions are not duplicated during source migration.
- JSONL parsing retains non-empty user and assistant text only; tool payloads
  remain outside retained conversational evidence.

## Verification

- Synthetic JSONL collection, incremental append, legacy fallback, source
  precedence, empty-header exclusion, and subagent exclusion tests.
- Cursor tests, full AWM pytest, Ruff, and viewer JavaScript gates.
- Reinstall the editable tool, run a real content-enabled Cursor sync, and
  compare retained Cursor sessions with both local source layouts.
