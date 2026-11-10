# Slice 198: Resume collection and reliable distillation

## Goal and contract

Repair the reported collection collision and Windows curator failure while
preserving slice 197: new events on a retained conversation make it pending
again; unchanged reads do not. A full-session curator merges existing Wiki
knowledge. Only the revision actually reviewed may be marked distilled.

The user requested implementation, verification, commit, and push. Work on
`codex/repair-resumed-session-distillation`; keep the installed editable checkout
available for the final authorized recovery. Tests use isolated state only.

## Approach

Keep the existing service boundaries. Prefer an exact source-path match before
the relocation heuristic; do not delete records or weaken SQLite uniqueness.
Pass captured session revisions to completion rather than reading the latest
revision at completion. Keep Windows sandboxing; remove app-only Core routing
from the standalone CLI child environment. Require an explicit curator handoff,
including an intentional empty result, instead of seeding a successful no-op.

## Tasks

- [x] Add failing isolated tests for path reuse with multiple missing histories,
  repeated collection, and new events arriving while distillation runs.
- [x] Fix identity lookup in services/sessions/service.py and snapshot completion
  in the session store/service and workflows/distill/service.py.
- [x] Add failing adapter tests for untouched/invalid/explicit-empty handoff and
  inherited desktop routing in integrations/curators/{yoke,hidden_codex}.py.
- [x] Fix the adapter contract without weakening sandbox/network permissions.
- [x] Check expired/exhausted automatic runs return an actionable CLI failure.
- [x] Run AWM pytest, Ruff, JavaScript syntax, and the broader test suite; review
  using .claude/agents/review.md and record fixes separately.
- [ ] Back up real state before recovery, run local collection and one manual
  Wiki batch, inspect receipts and changes, then commit and push code and Vault.

## Review focus

- Archive/resume moves preserve identity and already captured content.
- Similar provider IDs from different sources are not merged arbitrarily.
- New content during a curator run stays pending and remains visible in inbox.
- A failed or absent handoff cannot mark sessions completed or publish changes.
- Child environment isolation retains authentication and actual sandbox limits.

## Validation

Targeted tests must fail before implementation, then pass. Production recovery
is separate from tests and uses the user's explicit authorization. Do not claim
the full backlog is processed from a single successful batch.
