# Slice 186 - Resilient scheduled activity and curator metadata

## Intent

Make scheduled Activity truthful after an AWM worker disappears without its
normal completion callback, and prevent a curator rewrite of an existing Wiki
page from accidentally deleting required frontmatter.

The observed failures are distinct at the mechanism boundary:

- a scheduled process ended after writing its start record but before writing
  its finish record, leaving an Activity run permanently marked `running`;
- Codex rewrote existing durable pages without `short_title_ko`, so validation
  correctly rejected and rolled back otherwise useful distillation work.

## Shape

```python
runs = activity.list()
run = activity.begin(task, process_id)
# Both reads and the next start ask the process-liveness port about unfinished runs.
# A dead or reused PID becomes a durable failed run exactly once.

with vault.curator_workspace() as (workspace, baseline, original):
    curator.run(workspace)
    vault.preserve_curator_frontmatter(baseline)
    changed = vault.validate_distill_changes(baseline)
    vault.apply_distill_changes(workspace, changed)
```

The process probe is an integration owned by the composition roots. Activity
does not scrape Task Scheduler output or infer failure from elapsed time.

Frontmatter preservation applies only to pages that existed in the disposable
workspace baseline. Existing metadata remains present unless the curator
supplied a replacement value. Blank required bilingual titles are repaired
from the baseline. New pages still have to satisfy validation themselves.

## Work

1. Add a typed Activity process-liveness port and a psutil implementation.
2. Reconcile dead-process Activity runs when they are listed or superseded by
   the next start, and persist the interrupted failure state so the viewer
   cannot remain stuck on `Running`.
3. Ensure the scheduled wrapper records completion for ordinary base-level
   exits as well as regular exceptions.
4. Preserve existing page frontmatter in the curator workspace before strict
   validation, without weakening validation for new pages.
5. Cover stale PID recovery, live PID behavior, scheduled base exits, existing
   metadata repair, and new-page rejection with isolated tests.

## Safety

- Process inspection is read-only and access-denied results are treated as
  alive so AWM never falsely terminates another process's Activity.
- Reconciliation edits only AWM's private Activity ledger.
- Metadata repair edits only the disposable curator workspace. The original
  Vault still uses snapshot rollback and validated apply semantics.
- Tests use temporary state and Vault roots.

## Gates

```powershell
uv run pytest tests/test_agentworkmemory_scheduled.py tests/test_agentworkmemory_wiki.py tests/test_agentworkmemory_distill.py tests/test_agentworkmemory_viewer.py
uv run pytest tests/test_agentworkmemory*.py
uv run ruff check src/agentworkmemory tests/test_agentworkmemory*.py
node --check src/agentworkmemory/viewer/assets/app.js
```
