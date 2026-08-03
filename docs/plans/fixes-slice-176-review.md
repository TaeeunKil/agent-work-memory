# Fixes - Slice 176 review

## Review finding

- **Fix:** The dialog was labelled by the generic presentation context (for
  example, "Wiki page") rather than by the selected record's actual title.
  Give every primary detail heading one stable ID and use that heading as the
  dialog's accessible name.

## Resolution

1. Point `aria-labelledby` at `detail-peek-title`.
2. Apply that ID to the primary heading in every supported detail renderer.
3. Extend the packaged-surface test to assert the title contract.

No further architecture, correctness, naming, or duplication findings were
identified. Browser QA covers the residual interaction risk around history,
focus restoration, and full-screen sizing.
