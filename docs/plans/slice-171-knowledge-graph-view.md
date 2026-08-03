# Slice 171: Knowledge graph view

## Intent

Add a first-class Graph surface to the local AWM viewer. The graph maps durable
Wiki pages to nodes and resolved Wiki links to edges, then lets the user search,
filter, focus, and open the underlying Markdown without leaving the viewer.

## Shape

- The Wiki service owns resolution of page-to-page links.
- The Viewer service exposes a typed, presentation-ready graph contract.
- The FastAPI adapter publishes that contract at `GET /api/graph`.
- The browser renders the contract with a locally packaged Cytoscape.js asset.
- The existing page inspector remains the only Markdown detail surface.

## Interaction

- `Graph` is a primary navigation tab beside `Knowledge`.
- Search highlights and focuses matching nodes.
- Category filtering reduces the visible working set.
- Hover reveals a node's immediate neighborhood.
- Selecting a node opens the existing Wiki page inspector.
- Layout positions persist locally and can be reset explicitly.

## Verification

- Unit coverage for resolved Wiki links and the typed graph contract.
- Viewer API coverage for nodes, edges, headers, and packaged assets.
- JavaScript syntax and Python lint gates.
- Browser QA at desktop and narrow viewport sizes.
