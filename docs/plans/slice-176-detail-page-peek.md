# Slice 176 - Detail page peek

## Intent

Replace the narrow right-side inspector with a large, contextual detail peek.
Wiki pages, sessions, projects, activity runs, receipts, and the Wiki build
workflow should open in one consistent surface without destroying or resizing
the workspace behind them.

AppFlowy's database detail flow is the prior-art model: row details open in an
overlay, and the same content can be promoted to a full page. AWM borrows that
interaction shape while keeping its own restrained, document-first visual
language.

## Interaction shape

```text
workspace remains mounted
        |
        +-- open detail --> dim backdrop + wide paper surface
                                  |
                                  +-- expand --> full viewport, same content
                                  +-- close  --> exact workspace state returns
```

The peek owns presentation only. Existing detail functions continue to fetch
and render their domain content, then place it into the shared shell.

## Work

1. Replace the inspector DOM with an accessible dialog shell, backdrop, compact
   context label, expand control, close control, and scrollable content region.
2. Introduce shared open, close, expand, focus-trap, and focus-restoration
   behavior. Escape and backdrop clicks close the peek.
3. Move every existing inspector flow onto the shared surface so entry from a
   Wiki link, graph node, result row, or Activity view behaves consistently.
4. Make the regular peek a wide paper-like document over a dimmed workspace;
   make expanded mode fill the viewport, and use full-screen mode by default on
   narrow screens.
5. Preserve live Activity scroll following and keep the graph mounted so its
   zoom, filters, selection, and layout survive detail viewing.
6. Add viewer contract tests for the new DOM and behavior; remove stale
   inspector assumptions.

## Gates

```powershell
uv run pytest tests/test_agentworkmemory_viewer.py
uv run ruff check src/agentworkmemory tests/test_agentworkmemory_viewer.py
node --check src/agentworkmemory/viewer/assets/app.js
```
