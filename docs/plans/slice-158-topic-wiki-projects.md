# Slice 158 — Topic Wiki and project hubs

## Intent

Make durable knowledge, rather than individual sessions, the primary browsing
unit. Sessions remain evidence. Curators merge related evidence into one
canonical topic page and connect every topic to a project hub.

## Knowledge contract

- A durable page describes one topic, decision, problem, procedure, system, or
  unfinished thread; it is never a session summary.
- Existing pages are updated when new sessions concern the same topic.
- Every source session is retained in `sources` frontmatter.
- Every project has one `projects/<slug>.md` hub.
- Project-specific topic pages link to their project hub, and the hub links
  back to its topic pages.
- Session identifiers, dates, and agent names are not used as topic filenames.

## Viewer

- Add Projects as a primary surface.
- Project rows show connected topic and evidence counts.
- Selecting a project shows its hub, connected topic pages, and source
  sessions in the inspector.
- Add a Build Wiki action that explicitly distills the next bounded batch of
  pending sessions without requiring a terminal.
- Keep runtime and content-access selection visible at the action boundary.
- Reuse the same distillation coordinator as scheduled runs so viewer batches
  wait for synchronization instead of racing it.

## Verification

- Prompt tests assert canonical topic merging, project linking, workspace
  context, and source accumulation.
- Viewer tests assert project aggregation and bounded pending distillation.
- Existing path safety, content permission, and curator validation remain
  unchanged.
- Full AWM tests, Ruff, and viewer JavaScript checks pass.
