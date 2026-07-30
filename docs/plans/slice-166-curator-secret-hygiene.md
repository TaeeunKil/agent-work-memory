# Slice 166 — Curator secret hygiene

## Intent

Keep durable Wiki pages useful without copying authentication material from
selected work-session evidence.

## Shape

The shared curator instruction explicitly forbids persisting passwords,
tokens, API keys, private keys, session cookies, credential-bearing connection
strings, and raw authentication headers. When operational context matters, the
curator records only the role or delivery mechanism of the credential.

The rule is provider-independent and therefore applies to Codex, Claude, and
local curator runtimes that consume the shared instructions.

## Invariants

- Source session records remain unchanged.
- Durable pages retain useful architecture and procedure context.
- Secret values are omitted rather than transformed into reusable partials.
- The current ovion-251 batch is scanned separately because it completed before
  this instruction was added.

## Verification

- Prompt contract test asserts the forbidden secret classes and omission rule.
- Full pytest, Ruff, and viewer JavaScript gates.
