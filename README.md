# Agent Work Memory

**AWM** is a private local memory and Wiki for work performed with Codex,
Claude, local LLMs, and other coding agents.

It retains agent sessions across repositories, keeps the evidence searchable,
and promotes selected work into durable Markdown pages for decisions, systems,
problems, procedures, projects, and unfinished work.

## Install this fork

```powershell
git clone https://github.com/TaeeunKil/agent-work-memory.git
cd agent-work-memory
git switch codex/agent-work-memory
uv tool install --editable . --force
awm --help
```

## Set up your private memory

```powershell
awm setup C:\Users\user\Documents\AgentWorkMemoryVault `
  --include-content `
  --auto `
  --every 5
```

`--include-content` is explicit because transcripts may contain source code,
terminal output, internal paths, customer information, or secrets. Automatic
sync retains evidence only and never invokes a model.

## Daily use

```powershell
awm sync --from codex --from claude --include-content
awm sessions
awm search "why we chose sqlite"
awm serve
```

The viewer binds only to `127.0.0.1` and provides four working surfaces:

- **Today** — retained sessions, durable Wiki pages, and pending distillation
- **Sessions** — evidence from Codex, Claude, imports, and manual notes
- **Knowledge** — durable Markdown promoted from selected evidence
- **Activity** — running work, next scheduled work, receipts, and logs

## Distill sessions into the Wiki

```powershell
awm distill --pending --limit 3 `
  --using codex `
  --allow-remote-content
```

Automatic distillation is separate and opt-in:

```powershell
awm auto-distill install `
  --every 60 `
  --limit 1 `
  --for-days 2 `
  --max-total 6 `
  --using codex `
  --allow-remote-content
```

## SSH sources

Only explicitly registered SSH targets are read:

```powershell
awm remote add ovion-dev-157
awm remote list
awm remote sync ovion-dev-157 --include-content
```

AWM uses existing OpenSSH configuration and keys, reads bounded transcript
manifests, and does not write to remote machines.

## Local data

- Private runtime state: `%LOCALAPPDATA%\AgentWorkMemory`
- Durable Markdown: the Vault selected during `awm setup`
- Windows schedules: `AWM Sync` and `AWM Auto Distill`
- Python package: `agentworkmemory`

The Vault is ordinary Markdown and can be opened directly in Obsidian. Runtime
state may contain transcript bodies and should only be backed up to encrypted
storage.

See the [full user guide](docs/agent-work-memory-user-guide.md) for privacy,
runtime, import, recovery, and automation details.

## Fork structure

`src/agentworkmemory/` is the active AWM product. The upstream
`src/codealmanac/` tree remains in the checkout as unshipped reference source
for comparing and syncing the original project.

License: Apache-2.0.
