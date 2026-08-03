# Slice 181 review fixes

## Findings addressed

- Translation sidecars were initially eligible to become duplicate Wiki search
  identities. Search now folds every sidecar body into its canonical document,
  so either language can match while navigation and result identity stay
  canonical.
- Explicit translation runs had no model-level batch bound. The request model
  now rejects more than 20 pages, matching the pending-selection boundary.
- Legacy language inference treated any Hangul link alias as proof that the
  whole page was Korean. It now uses the relative Hangul and Latin character
  weight, with a regression test for English prose containing a Korean link.

## Residual risk

- Locale inference remains a compatibility path for legacy pages without a
  `language` field. Newly distilled pages are instructed to write the field,
  and translations record their locale explicitly.
