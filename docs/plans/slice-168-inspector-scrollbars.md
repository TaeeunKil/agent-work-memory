# Slice 168 — Inspector scrollbars

## Intent

Replace the visually heavy default scrollbars in the Activity inspector and
live-log viewport with quiet, narrow controls that reveal themselves on
interaction.

## Fit

This is presentation owned entirely by the existing viewer stylesheet. Native
scrolling remains the mechanism; no JavaScript scroll emulation or new
component lifecycle is warranted.

## UI direction

- Visual thesis: a slim, rounded neutral rail that recedes into the dark
  inspector surface.
- Content plan: no content changes; the scrollbar supports the existing run
  timeline and recent log.
- Interaction thesis:
  - The track and thumb are transparent at rest.
  - Hovering or focusing a scroll region reveals a restrained thumb.
  - Hovering the thumb increases contrast without introducing a second accent.

## Browser shape

```text
Firefox
  scrollbar-width: thin
  scrollbar-color: transparent → paper/transparent on interaction

Chromium / WebKit
  7px transparent track
  rounded transparent thumb → paper thumb on interaction
```

Keyboard focus is treated like pointer hover so the control does not disappear
for keyboard users. The live log remains focusable and uses native scrolling.

## Verification

- Assert that the served CSS includes idle, hover, and keyboard-focus states.
- Run the viewer test module and standard AWM gates.
- Review against `.claude/agents/review.md` and record fixes.
