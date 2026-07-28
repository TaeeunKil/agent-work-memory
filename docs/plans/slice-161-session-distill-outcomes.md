# Slice 161 — Auditable session distillation outcomes

## Intent

AWM should not create a page for every retained session. It should still show
that each selected session was reviewed and why it did or did not contribute to
durable knowledge.

## Shape

- Classify each selected session from the durable Wiki state before and after
  the curator runs.
- Persist one typed outcome per session on the distillation receipt.
- Use four outcomes: created, merged, already covered, and no durable knowledge.
- Keep classification provider-neutral and deterministic; do not scrape curator
  prose for product state.
- Show outcome counts in scheduled logs and per-session details in Activity.

## Verification

- A new cited page classifies its source session as created.
- A changed existing cited page classifies it as merged.
- An unchanged page that already cites the session classifies it as already
  covered.
- A reviewed session without a durable citation classifies it as no durable
  knowledge.
- Old receipts remain readable with an empty outcome list.
