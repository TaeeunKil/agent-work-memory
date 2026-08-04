# Slice 184 review fixes

## Finding

The canonical uv-tool fallback was selected correctly, but an explicitly
configured relative `UV_TOOL_DIR` could have produced a relative Task Scheduler
action. The default `%APPDATA%` fallback also lacked direct test coverage.

## Fixes

1. Resolve configured uv-tool roots to absolute paths before composing task
   actions.
2. Cover the default `%APPDATA%\uv\tools\agent-work-memory` fallback with an
   isolated synthetic-PE test.

## Residual risk

AWM cannot repair an existing task until its action is re-registered. The live
tasks therefore need an explicit post-change path check.
