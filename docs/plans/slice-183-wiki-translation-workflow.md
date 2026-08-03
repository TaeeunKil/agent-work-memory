# Slice 183 — Wiki translation workflow

## Intent

Create or refresh derived Korean and English Markdown representations without
making translation success a prerequisite for durable distillation.

## Shape

- Add a translation-specific workflow over the existing curator runtime port.
- Select canonical pages whose requested representation is missing or stale.
- Translate prose and display aliases while preserving paths, Wiki targets,
  source identifiers, citations, code, and configuration keys.
- Validate generated sidecars and apply them atomically under `translations/`.
- Expose bounded CLI commands for one page and pending translations.

## Verification

- Translation failure leaves canonical pages unchanged.
- Only the requested translation sidecars may change.
- Current translations no-op; stale translations refresh.
- Generated files retain provenance and match the canonical digest.
