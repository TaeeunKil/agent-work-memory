# Agent Work Memory User Guide

Agent Work Memory is a private local Wiki for work performed with Codex Desktop,
Claude, Cursor, local LLMs, and provider-neutral imported agent records.

The durable Wiki is ordinary Markdown. Open it with Obsidian, browse it with the
local Agent Work Memory viewer, version it with Git, or back it up like any other
folder.

## Install from this checkout

Install `uv`, then run this repository's main branch:

```powershell
git switch main
uv tool install --editable . --force
awm --help
```

The installed distribution is `agent-work-memory`. Its commands are `awm` and
`agent-work-memory`; the upstream CodeAlmanac reference source in this checkout
is not shipped as a second CLI.

## One-time setup

Choose one private Vault directory:

```powershell
awm setup C:\Users\user\Documents\AgentWorkMemoryVault
```

That initializes the Vault and discovers Codex, Claude, and Cursor sessions using
metadata only.

To retain transcript bodies locally and install five-minute automatic sync:

```powershell
awm setup C:\Users\user\Documents\AgentWorkMemoryVault `
  --include-content `
  --auto `
  --every 5
```

`--include-content` is explicit because transcripts can contain code, command
output, paths, customer data, and secrets. Scheduled synchronization never
invokes a curator or remote model.

Check the result:

```powershell
awm doctor
awm auto status
awm sessions
```

## Daily use

Automatic sync is enough for routine retention. Manual commands remain
available:

```powershell
awm sync --from codex --from claude --from cursor --include-content
awm search "why we chose sqlite"
awm sessions
awm show ses_...
```

Open the local viewer:

```powershell
awm serve
```

The viewer binds only to `127.0.0.1`. It shows retained sessions, durable Wiki
pages, source links, backlinks, search results, and body-free operation
receipts.

### What Cursor collection includes

The `cursor` provider reads native Cursor Composer conversations from Cursor's
local SQLite store. Workspace identifiers are retained for local folders, WSL,
and Cursor Remote SSH sessions.

Codex used inside Cursor through the OpenAI Codex extension uses Codex's
standard `.codex` store, so those sessions are already collected by the
`codex` provider. A Claude extension or terminal session that writes Claude's
standard `.claude` store is collected by the `claude` provider. AWM keeps these
native records under their native provider rather than duplicating them as
Cursor Composer sessions.

## Open in Obsidian

1. Open Obsidian.
2. Choose **Open folder as vault**.
3. Select `C:\Users\user\Documents\AgentWorkMemoryVault`.
4. Open `Home.md`.

Generated navigation files are marked `agentworkmemory_managed: true`. Do not edit
`Home.md` or `_index.md` files by hand; they are safe to regenerate.

The Wiki areas are:

```text
inbox/agent-sessions/          retained evidence
projects/                      project state and context
decisions/                     decisions and rationale
problems/                      solved and recurring problems
procedures/                    repeatable procedures
systems/                       machine and system context
unfinished/                    concrete next work
imports/repository-almanacs/   isolated legacy Wiki review
```

Synchronization fills `inbox/agent-sessions` and the private search database.
Large retained sessions keep their normal session page as an index and store
the record in deterministic `part-001.md`, `part-002.md`, and later files. Each
part is bounded below AWM's Vault publication limit. `awm vault publish`,
`push`, and `sync` refuse to stage any remaining file above 48 MiB and tell you
to refresh the owning session first.

It does not create pages in `projects`, `decisions`, `problems`, `procedures`,
`systems`, or `unfinished`. Those are durable knowledge and change only when
you explicitly distill selected sessions. `awm doctor` reports how many
captured sessions are waiting for that step.

## Collect from SSH machines

Agent Work Memory can pull Codex and Claude JSONL transcripts from explicit OpenSSH
targets. Use an alias already configured in `~/.ssh/config`, or `user@host`:

```powershell
awm remote add agent-box
awm remote list
awm remote sync agent-box --include-content
```

Once registered, the remote is included automatically in ordinary `awm sync`
and installed automatic-sync runs. Use these commands to inspect or remove it:

```powershell
awm remote status agent-box
awm remote remove agent-box
```

The target must already be trusted in `known_hosts` and support non-interactive
key authentication plus `python3`. Agent Work Memory uses OpenSSH batch mode, never
prompts for a password, does not scan every SSH config entry, and does not
write to the remote machine. It first reads a bounded manifest, then downloads
only changed `.jsonl` files into private local state. Removing a registration
keeps records already retained in the Vault and database.

## Distill selected work

Metadata-only is the default:

```powershell
awm distill ses_... --using codex
```

Allow selected content to a remote runtime explicitly:

```powershell
awm distill ses_... --using codex --allow-remote-content
awm distill ses_... --using claude --allow-remote-content
```

Select the newest captured sessions that have not been distilled without
copying IDs by hand:

```powershell
awm distill --pending --limit 3 --using codex --allow-remote-content
```

`--pending` defaults to three sessions and accepts a limit from 1 through 20.
The selected IDs are printed before curator execution. It never includes
metadata-only or already-distilled sessions.

Install a separate, opt-in automatic distillation task after testing one
manual run:

```powershell
awm auto-distill install `
  --every 60 `
  --limit 1 `
  --using codex `
  --allow-remote-content
```

Inspect, exercise, or remove it:

```powershell
awm auto-distill status
awm auto-distill run
awm auto-distill remove
```

The standing content grant is mandatory. Each run selects only the configured
number of captured, not-yet-distilled sessions. Automatic sync remains a
separate evidence-only task, and curator failures use the same validated
workspace and rollback path as manual distillation.

The standing grant expires after 7 days or 24 reserved session attempts by
default, whichever comes first. An attempt consumes its allowance before the
curator runs, even if that run later fails. Narrow it further when desired:

```powershell
awm auto-distill install `
  --every 60 --limit 1 `
  --for-days 2 --max-total 6 `
  --using codex --allow-remote-content
```

Use a local Ollama model:

```powershell
ollama pull qwen3:8b
awm runtimes
awm distill ses_... `
  --using ollama `
  --model qwen3:8b `
  --allow-local-content
```

The local adapter accepts only a loopback HTTP endpoint and gives the model no
shell or direct filesystem tools. Structured complete-file changes still pass
through the same disposable workspace, Markdown validation, and rollback path.

## Other agents

Any agent can emit a provider-neutral JSON record:

```json
{
  "provider": "ollama.qwen",
  "session_id": "local-42",
  "title": "Architecture review",
  "cwd": "C:\\work\\project",
  "events": [
    {
      "kind": "message",
      "role": "assistant",
      "content": "Keep provider shapes at the collector edge."
    }
  ]
}
```

Import it:

```powershell
awm import C:\path\to\record.json
```

## Import old repository Almanacs

Existing repository Wikis are copied into an isolated review namespace. The
source repository is never modified:

```powershell
awm migrate-almanac C:\path\to\old-repository
```

Only UTF-8 Markdown below `.almanac/pages` is copied. Non-Markdown files are
ignored, symlinks are rejected, and the total import is limited to 50 MB.

## Privacy and backup

Two locations contain private data:

- the configured Markdown Vault;
- `%LOCALAPPDATA%\AgentWorkMemory`, which contains SQLite state, retained event
  bodies, cursors, receipts, SSH transcript snapshots, and disposable-runtime
  state.

Back up the Vault for durable knowledge. Back up local state only to encrypted
storage if you need the retained evidence database as well. Do not publish the
Vault or state directory without reviewing transcript content.

Curator rules:

- metadata-only never sends event bodies or title-derived manual-note content;
- local-content works only with the loopback Ollama adapter;
- remote-content requires `--allow-remote-content`;
- scheduled sync never performs distillation;
- curator work happens in an inbox-free disposable Vault;
- only validated durable Markdown changes reach the actual Vault.

## Recovery

Inspect health:

```powershell
awm doctor --runtimes
awm auto status
```

Run one safe incremental retry:

```powershell
awm sync --from codex --from claude --from cursor --include-content
```

Reinstall automatic sync:

```powershell
awm auto remove
awm auto install --every 5 --from codex --from claude --from cursor --include-content
```

The Markdown Vault remains the durable source of truth. Search indexes,
operation receipts, and generated navigation can be rebuilt from the Vault and
retained sessions.
