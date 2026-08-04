# Slice 184: canonical Windows scheduled runtime

## Intent

Keep AWM background tasks invisible and independent of the environment that
ran `auto install` or `auto-distill install`.

Project virtual environments can contain a `pythonw.exe` launcher whose PE
subsystem is still Console. Registering that path with Task Scheduler creates
`conhost.exe` and flashes a terminal window on every interval.

## Shape

```python
runtime = scheduled_runtime.resolve(sys.executable, environment)

runtime.current_pythonw   # preferred when it is a real GUI executable
runtime.uv_tool_pythonw   # canonical installed AWM fallback
runtime.require_hidden()  # refuse to register a console-backed task
```

Both `AWM Sync` and `AWM Auto Distill` continue to use the shared
`background_python_executable()` boundary. The resolver checks the Windows PE
subsystem instead of trusting the filename and falls back to the canonical uv
tool installation under `UV_TOOL_DIR` or `%APPDATA%\uv\tools`.

## Work

1. Detect whether a Windows executable uses the GUI subsystem.
2. Prefer the current environment only when its `pythonw.exe` is genuinely
   consoleless.
3. Otherwise use the canonical `agent-work-memory` uv-tool runtime.
4. Fail clearly instead of installing a task that will flash a console.
5. Cover current-runtime, fallback, and refusal behavior with isolated tests.
6. Re-register both live Windows tasks against the canonical runtime.

## Safety

- Do not change grants, collection scope, remote registrations, or schedules.
- Do not copy or relocate Python runtimes.
- Do not rely on repository paths in Task Scheduler actions.
- Tests use synthetic PE files and temporary directories.

## Gates

```powershell
uv run pytest tests/test_agentworkmemory_sync.py tests/test_agentworkmemory_auto_distill.py
uv run ruff check src/agentworkmemory tests/test_agentworkmemory_sync.py tests/test_agentworkmemory_auto_distill.py
```
