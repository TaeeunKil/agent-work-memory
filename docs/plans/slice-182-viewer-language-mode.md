# Slice 182 — Viewer language mode

## Intent

Provide persistent Korean and English modes across viewer chrome, Wiki labels,
graph labels, and page bodies while preserving the current route and graph
layout.

## Visual thesis

Treat language as a quiet workspace preference: a compact typographic switch
in the sidebar footer, with no flags, extra panel, or competing accent.

## Interaction thesis

- Switch all chrome and labels in place without a reload.
- Keep graph positions, filters, selection, and the open Wiki page stable.
- Let an open Wiki page temporarily show its original independently of the
  global preference.

## Shape

- Add one dependency-free browser locale module with matching Korean and
  English message catalogs.
- Persist the preference in browser storage and update the document `lang`.
- Render graph and list labels from both short titles using a deterministic
  fallback.
- Request localized page bodies from the existing canonical route.
- Surface missing or stale translation state inside the Wiki page header.

## Verification

- Catalog key parity and fallback behavior are tested.
- Packaged assets remain offline and CSP-compatible.
- Switching locale does not rebuild graph layout state or change Wiki routes.
