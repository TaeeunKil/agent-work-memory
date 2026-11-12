# Slice 199: Portable CI tests

## Goal

Repair the eight failures reproduced in Linux CI without changing application
behavior. The preceding commit failed with the same eight tests; the affected
test files pass all 73 tests on Windows.

## Approach

- Use native temporary workspace paths for Cursor collection fixtures.
- Keep explicit Windows URI coverage with host-specific path expectations.
- Exercise Windows and Linux process flags explicitly in the subprocess adapter
  tests, independently of the host running pytest. Substitute the process
  helper's platform source without changing the interpreter's global platform.
- Preserve UTF-8, buffering, environment isolation, and ACL assertions.
- Run the complete suite and lint on Windows and Linux, plus the CLI smoke test
  and viewer JavaScript syntax check. Review against `.claude/agents/review.md`.

## Scope

Tests and review notes only. No changes to collectors, process flags, private
state, Vault contents, or CI platform selection.
