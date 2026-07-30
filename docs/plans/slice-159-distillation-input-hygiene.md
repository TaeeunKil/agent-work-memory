# Slice 159 — Distillation input hygiene

## Incident

A 20-session bulk Wiki build changed no pages while marking all selected
sessions distilled. The batch mixed real projects with AWM-created curator
workspaces and diagnostic sessions. Its 62 million retained characters were
truncated to a 120,000-character prompt, so each unrelated session contributed
only a small prefix.

## Corrections

- Exclude AWM state, `distill-workspaces`, ACL probes, and pytest workspaces
  from collection and distillation eligibility.
- Keep excluded records as evidence but never promote them into durable Wiki.
- Select viewer batches from one workspace at a time.
- Build evidence from the first intent and recent conversational outcomes,
  rather than filling the budget with the earliest tool output.
- Add an explicit requeue operation for incorrectly completed sessions.
- Repair the interrupted receipt and requeue the incident batch before retrying.

## Verification

- Internal curator and diagnostic workspaces are not collected or counted as
  pending knowledge.
- A project batch never mixes distinct known workspaces.
- Long sessions retain their opening intent and latest useful messages while
  omitting oversized intermediate tool logs.
- Requeued sessions become eligible again without deleting their retained
  evidence.
