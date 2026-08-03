# Slice 178 - Stable sidebar brand transition

## Intent

Remove the visible line-wrap flash from the Agent Work Memory brand when the
desktop sidebar expands. The rail width and brand name currently change at
different times: the name returns from `display: none` before enough width is
available, so the browser briefly reflows it.

## Interaction shape

```text
collapsed              expanding                 expanded
+ AWM +       ->       + AWM + rail grows ->     + AWM Agent Work +
                                                  +     Memory     +
                       name remains transparent   name fades in
```

## Work

1. Give the brand a stable 37-pixel anchor and position the two-line product
   name independently of the rail's changing content width.
2. Keep the forced two-line shape throughout the transition instead of
   toggling layout with `display`.
3. Hide the name immediately while collapsing and reveal it only after the
   expanding rail has enough room.
4. Preserve the existing compact tablet/mobile behavior where the name is not
   shown.
5. Add a viewer asset contract test and visually verify repeated collapse and
   expansion.

## Gates

```powershell
uv run pytest tests/test_agentworkmemory_viewer.py
uv run ruff check src/agentworkmemory tests/test_agentworkmemory_viewer.py
node --check src/agentworkmemory/viewer/assets/app.js
```
