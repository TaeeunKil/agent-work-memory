# Slice 180 — Drain large distillation backlogs

## Intent

Allow an owner to grant enough bounded automatic-distillation capacity to
drain a large existing backlog without repeatedly renewing a 100-session
grant.

## Shape

- Keep automatic distillation explicitly granted, finite, and expiring.
- Raise the validation ceiling from 100 to 1,000 sessions.
- Keep the default grant at 24 sessions and the per-run limit at 20 or less.
- Configure the current machine for exactly the current pending backlog rather
  than an unbounded grant.

## Verification

- Prove a 439-session standing grant is accepted.
- Prove a grant above 1,000 sessions is rejected.
- Run the focused automatic-distillation tests and the standard AWM gates.

