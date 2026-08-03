# Slice 177 - Detail page table of contents

## Intent

Add a restrained, navigable table of contents to long Wiki and project pages
inside the detail peek. Keep the document as the dominant surface while making
long pages easier to scan and traverse.

## Interaction shape

```text
desktop                         narrow viewport
+ document body + on this page + + collapsed On this page +
| h2 section    | active h2     | | document body           |
| h3 subsection |   h3          | |                         |
+---------------+---------------+ +-------------------------+
```

The table of contents is derived from the rendered Markdown currently in the
peek. It is presentation state only and does not change Wiki Markdown or the
page URL.

## Work

1. Add a dedicated table-of-contents region beside the existing scrollable
   detail content.
2. Collect rendered Markdown `h2` and `h3` headings, assign local stable
   targets, and hide the region when fewer than two useful headings exist.
3. Smooth-scroll to a selected heading without changing the Wiki route hash.
4. Track the current reading section as the detail content scrolls and expose
   it through `aria-current` and the warm accent.
5. Switch the right rail to a compact disclosure above the document on narrow
   viewports.
6. Test the packaged DOM, heading collection, scroll navigation, and active
   section contracts; visually verify desktop and narrow layouts.

## Gates

```powershell
uv run pytest tests/test_agentworkmemory_viewer.py
uv run ruff check src/agentworkmemory tests/test_agentworkmemory_viewer.py
node --check src/agentworkmemory/viewer/assets/app.js
```
