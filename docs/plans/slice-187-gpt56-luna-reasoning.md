# Slice 187: GPT-5.6 Luna reasoning controls

## Intent

Expose the Codex model and reasoning effort used by direct and scheduled Wiki
distillation. The requested model is `gpt-5.6-luna`; the accepted effort values
are `low`, `medium`, `high`, `xhigh` (also accepted as “extra high”), and
`max`.

## Shape

```text
CLI --model/--effort
  -> typed request/settings (ReasoningEffort)
  -> distillation/translation workflow
  -> CuratorRunRequest
  -> Yoke RunOptions(effort="xhigh" | "max")
  -> Codex CLI model_reasoning_effort config
```

Scheduled configuration changes must update only model and effort. They must
preserve the existing expiry, content-access grant, reservation count, and
operating-system task, so changing the model cannot silently create a new
standing grant.

## Verification

- Model and effort survive Auto Distill settings persistence and workflow
  propagation.
- The Codex adapter maps the typed effort to Yoke's string-valued option.
- CLI accepts `extra high`/`extra-high` as `xhigh` and reports the active
  model/effort in status and install output.
- Existing AWM tests, Ruff, JavaScript syntax, and diff checks pass.
