# Slice 167 — Live log following

## Intent

Keep the Activity inspector anchored to the newest log output while a scheduled
operation is running. Refreshing the two-second activity snapshot must not jump
the inspector or its log viewport back to the top.

## Fit

This is viewer interaction policy, not activity-service behavior. The existing
`openScheduledActivity` refresh boundary already owns replacement of the
inspector markup, so it should capture and restore end-aware scroll state around
that replacement. No persistence or backend contract is needed.

## UI direction

- Visual thesis: preserve the restrained operations panel and make the live log
  feel like a stable terminal tail.
- Content plan: keep the run header, timeline, and recent-log hierarchy exactly
  as-is.
- Interaction thesis:
  - Opening a run starts at the newest output.
  - A viewer already near the bottom follows newly appended output.
  - Scrolling upward opts out of following until the viewer returns to the
    bottom.

## Shape

```text
snapshot = endAwareScroll.capture(inspector, log)
inspector.render(activity)
endAwareScroll.restore(inspector, log, snapshot)
```

Both the outer inspector and the nested log viewport use the same near-end
policy. A small tolerance avoids disabling follow mode because of fractional
layout measurements.

## Verification

- Add an asset contract test for the live-log scroll markers and policy.
- Run the AWM viewer tests.
- Run the standard AWM Python, Ruff, and JavaScript syntax gates.
- Review against `.claude/agents/review.md` and record any fixes.
