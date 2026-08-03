# Fixes - Slice 177 review

## Review findings

- **Fix:** Generated table-of-contents targets replaced any heading IDs already
  emitted by Markdown, which could break authored in-page links. Preserve
  existing IDs and generate a local target only when a heading has none.
- **Fix:** The navigation followed the entire document in DOM order even though
  it appeared beside or above the document. Put the navigation before the
  content in source order and use named grid areas to retain the desktop
  composition. This makes keyboard traversal match the visual reading order.
- **Polish:** Truncated desktop labels need a native hover title so their full
  text remains discoverable.

## Resolution

1. Preserve authored heading identifiers and add targets only to unlabelled
   headings.
2. Reorder the detail body source and explicitly assign `toc` and `content`
   layout areas.
3. Copy each heading's complete text to the generated control's title.
4. Re-run viewer, lint, JavaScript, and visual interaction gates.
