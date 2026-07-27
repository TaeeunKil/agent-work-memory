# Major Findings

## 1. The current center of gravity is wrong

### Finding

`Repository` is not merely one entity. It owns selection, source matching, run
identity, working directory, Markdown location, mutation safety, index location,
viewer scope, and automation grouping.

### Evidence

- `src/codealmanac/services/repositories/models.py`
- `src/codealmanac/services/repositories/service.py`
- `src/codealmanac/workflows/sync/evaluation.py`
- `src/codealmanac/services/runs/models.py`
- `src/codealmanac/workflows/operations/service.py`

### Architectural cost

Non-repository tasks, nested working directories, multi-project sessions,
Windows/WSL aliases, and SSH work all become exceptions around one overloaded
owner.

### Recommendation

Redesign around one personal `Vault`. Repositories become optional `Project`
and `Artifact` evidence.

### Confidence

High.

## 2. Source normalization is too lossy and too late

### Finding

Transcript adapters discover typed provider records, but runtime inspection
ultimately renders them into one bounded prompt string.

### Evidence

- `src/codealmanac/integrations/sources/transcripts/models.py`
- `src/codealmanac/integrations/sources/transcripts/entries.py`
- `src/codealmanac/integrations/sources/transcripts/rendering.py`
- `src/codealmanac/integrations/sources/transcripts/runtime.py`

### Architectural cost

Stable provider ids, timestamps, event kinds, tool outcomes, and cursor
positions are harder to deduplicate, query, retain, redact, or correlate after
they become prose. Tail truncation may also remove the decision context that
made later actions meaningful.

### Recommendation

Normalize into typed capture events first. Render bounded evidence only when a
curator run reads selected sessions.

### Confidence

High.

## 3. Current sync semantics are unsuitable for reliable personal capture

### Finding

Sync exact-matches transcript cwd to a registered root, filters by transcript
modification time, groups by repository, queues ingest, and advances one global
completion timestamp.

### Evidence

- `src/codealmanac/workflows/sync/evaluation.py`
- `src/codealmanac/workflows/sync/queue.py`
- `src/codealmanac/workflows/sync/store.py`

### Architectural cost

It cannot represent per-source cursors, partial transcript growth, duplicate
delivery, nested workspaces, non-repo work, multi-host clocks, or completion of
the actual distillation work.

### Recommendation

Delete this workflow and replace it with per-source cursor-aware `collect`.
Reserve `sync` for future node transport.

### Confidence

High.

## 4. Platform support is a composition bug, not a scheduler-service bug

### Finding

The scheduler is correctly behind `SchedulerAdapter`, but the composition root
always constructs `LaunchdSchedulerAdapter`.

### Evidence

- `src/codealmanac/services/automation/ports.py`
- `src/codealmanac/app.py`
- `src/codealmanac/integrations/automation/scheduler/launchd.py`

### Recommendation

Keep the seam. Add platform selection and implement Windows Task Scheduler
first. Do not branch on OS inside automation policy.

### Confidence

High.

## 5. The curator seam is good; the provider catalog is premature policy

### Finding

Harness adapters already isolate provider execution, but enums and config
hard-code Codex/Claude and a central model catalog.

### Evidence

- `src/codealmanac/services/harnesses/ports.py`
- `src/codealmanac/services/harnesses/kinds.py`
- `src/codealmanac/services/config/models.py`
- `src/codealmanac/integrations/harnesses/yoke/adapter.py`

### Recommendation

Preserve the typed runner seam. Do not build a generic plugin registry. Rename
the product concept to curator and add one local adapter only when a concrete
tool-capable runner is selected and tested.

### Confidence

High.

## 6. Release machinery is distracting from the new product proof

### Finding

Auto-update and anonymous telemetry are substantial product surfaces with
security, configuration, scheduling, testing, and documentation costs.

### Evidence

- `src/codealmanac/services/updates/`
- `src/codealmanac/services/telemetry/`
- `src/codealmanac/integrations/updates/`
- `src/codealmanac/integrations/telemetry/`

### Recommendation

Freeze or remove them from the first Work Almanac slices. Reintroduce only
after there is an actual installation and distribution strategy.

### Confidence

Medium-high.
