# Fixes — Slice 173 review

## Findings addressed

- Route shell transitions through the existing graph resize timer with a single delay so Cytoscape refreshes immediately after the rail animation.
- Close any active custom listbox as part of graph teardown so detached controls are not retained after navigation.
- Remove redundant compact-navigation padding and verify the mobile rail owns no horizontal overflow.
- Give graph legend swatches an explicit display mode and fixed flex basis, then move category colors from CSP-blocked inline styles to static CSS classes.

## Verification

- Re-run the viewer and full AWM test suites.
- Re-run Ruff, JavaScript syntax, and scoped diff checks.
- Confirm the desktop rail transition, listbox keyboard flow, persistence, and 390px mobile layout in the local browser.
