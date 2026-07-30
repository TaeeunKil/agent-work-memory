# Slice 160 review fixes

## Finding

- **Fix:** The first `HiddenCodex` constructor exposed fewer options than the
  Yoke adapter it wraps. That unnecessarily narrowed the provider contract and
  could prevent future additional-directory use.

## Correction

- Preserve and forward Yoke's `additional_directories` argument while replacing
  only its process-launch mechanism.

## Residual risk

- `HiddenCodexCli` mirrors Yoke's small JSONL bridge because Yoke 0.1.x does not
  expose subprocess creation flags. A future Yoke release with a supported
  process-options seam should replace this wrapper.
