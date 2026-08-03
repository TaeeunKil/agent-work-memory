# Slice 183 review fixes

## Findings addressed

- Translation failure is isolated from successful distillation: the scheduler
  reports deferral and retains the completed canonical Wiki update.
- Translation workspace output is accepted only when exactly the selected
  canonical path changed and the resulting Markdown contains an H1.
- Missing and invalid sidecars fall back to the canonical body; stale sidecars
  remain visible with an explicit stale notice and can be regenerated.

## Residual risk

- Runtime translation quality is agent-dependent. Tests exercise the complete
  workflow boundary with a fake curator, while real Codex, Claude, and Ollama
  runs remain an operational integration concern.
