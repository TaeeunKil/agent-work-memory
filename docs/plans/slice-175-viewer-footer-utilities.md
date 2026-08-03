# Slice 175 - Viewer footer utilities

## Intent

Move the global search, transcript sync, and Wiki build controls from the top
of the workspace to a restrained bottom utility bar. Remove that global chrome
entirely from Graph so the knowledge canvas uses the full available height.

## Layout

```text
regular view                  graph view
+ rail + workspace +         + rail + graph toolbar +
|                      |      |                      |
|                      |      |   full graph canvas  |
+ search / sync / build+      +----------------------+
```

The graph's own title, node search, category filter, fit, and re-layout controls
remain at the top because they operate directly on that view.

## Work

1. Move the existing utility DOM below the workspace and use a semantic footer.
2. Keep the footer at the bottom of ordinary views without introducing a card
   or floating dock treatment.
3. Hide the footer whenever `workspace.graph-workspace` is active.
4. Recalculate desktop and mobile graph heights without the former header.
5. Verify search/action bindings still use the existing stable element IDs.

## Gates

```powershell
uv run pytest tests/test_agentworkmemory_viewer.py
uv run ruff check src/agentworkmemory tests/test_agentworkmemory_viewer.py
node --check src/agentworkmemory/viewer/assets/app.js
```
