# Slice 173 — Viewer navigation controls

## Intent

Keep graph controls legible across Windows browser themes and let desktop users reclaim workspace width without losing primary navigation.

## Shape

- Replace the graph category native select with a reusable, theme-owned listbox component.
- Preserve pointer and keyboard selection, visible focus, selected state, and outside-click dismissal.
- Add a desktop rail toggle that collapses the navigation to a compact glyph rail.
- Persist the user's rail preference locally and resize the knowledge graph after the shell transition.
- Leave the mobile top navigation independent from the desktop rail preference.

## Invariants

- Graph category filtering continues to update visible node and edge counts.
- Dropdown text and selected options retain strong contrast without relying on operating-system select styling.
- Every compact navigation glyph keeps an accessible text label and hover title.
- The rail can always be restored from its collapsed state.
- Reduced-motion preferences suppress decorative transitions.

## Verification

- Viewer asset contract checks for the listbox and rail toggle surfaces.
- Full AWM pytest, Ruff, JavaScript syntax, and diff checks.
- Browser QA for pointer and keyboard dropdown use, rail persistence, graph resizing, and mobile navigation.
