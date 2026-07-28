# Slice 160 — Hidden Windows child processes

## Intent

Scheduled AWM work already starts through `pythonw.exe`, but SSH and curator
subprocesses can still allocate transient console windows. Every subprocess
owned by AWM should follow one Windows background-process policy.

## Shape

- Define the Windows `CREATE_NO_WINDOW` flag once at the integrations boundary.
- Apply it to SSH capture/download, scheduler commands, PowerShell schedule
  inspection, Vault ACL repair, Codex app-server, Codex CLI execution, and
  Codex readiness checks.
- Keep non-Windows behavior unchanged.
- Do not patch installed third-party files; wrap Yoke's Codex CLI adapter from
  AWM so upgrades do not erase the fix.

## Verification

- Windows subprocess calls receive `CREATE_NO_WINDOW`.
- The wrapped Codex CLI preserves JSONL streaming and readiness behavior.
- Existing sync, distillation, scheduling, and Wiki tests remain green.
