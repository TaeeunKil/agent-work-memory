# Work Almanac User Guide

Work Almanac is a private local Wiki for work performed with Codex Desktop,
Claude, local LLMs, and provider-neutral imported agent records.

The durable Wiki is ordinary Markdown. Open it with Obsidian, browse it with the
local Work Almanac viewer, version it with Git, or back it up like any other
folder.

## Install from this checkout

Install `uv`, then run this repository's Work Almanac branch:

```powershell
git switch codex/workalmanac
uv tool install --editable . --force
wa --help
```

The package currently retains the upstream `codealmanac` distribution name so
the original CLI remains available. Work Almanac uses the separate `wa` and
`workalmanac` commands and independent local state.

## One-time setup

Choose one private Vault directory:

```powershell
wa setup C:\Users\user\Documents\WorkAlmanacVault
```

That initializes the Vault and discovers Codex and Claude sessions using
metadata only.

To retain transcript bodies locally and install five-minute automatic sync:

```powershell
wa setup C:\Users\user\Documents\WorkAlmanacVault `
  --include-content `
  --auto `
  --every 5
```

`--include-content` is explicit because transcripts can contain code, command
output, paths, customer data, and secrets. Scheduled synchronization never
invokes a curator or remote model.

Check the result:

```powershell
wa doctor
wa auto status
wa sessions
```

## Daily use

Automatic sync is enough for routine retention. Manual commands remain
available:

```powershell
wa sync --from codex --from claude --include-content
wa search "why we chose sqlite"
wa sessions
wa show ses_...
```

Open the local viewer:

```powershell
wa serve
```

The viewer binds only to `127.0.0.1`. It shows retained sessions, durable Wiki
pages, source links, backlinks, search results, and body-free operation
receipts.

## Open in Obsidian

1. Open Obsidian.
2. Choose **Open folder as vault**.
3. Select `C:\Users\user\Documents\WorkAlmanacVault`.
4. Open `Home.md`.

Generated navigation files are marked `workalmanac_managed: true`. Do not edit
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
It does not create pages in `projects`, `decisions`, `problems`, `procedures`,
`systems`, or `unfinished`. Those are durable knowledge and change only when
you explicitly distill selected sessions. `wa doctor` reports how many
captured sessions are waiting for that step.

## Collect from SSH machines

Work Almanac can pull Codex and Claude JSONL transcripts from explicit OpenSSH
targets. Use an alias already configured in `~/.ssh/config`, or `user@host`:

```powershell
wa remote add agent-box
wa remote list
wa remote sync agent-box --include-content
```

Once registered, the remote is included automatically in ordinary `wa sync`
and installed automatic-sync runs. Use these commands to inspect or remove it:

```powershell
wa remote status agent-box
wa remote remove agent-box
```

The target must already be trusted in `known_hosts` and support non-interactive
key authentication plus `python3`. Work Almanac uses OpenSSH batch mode, never
prompts for a password, does not scan every SSH config entry, and does not
write to the remote machine. It first reads a bounded manifest, then downloads
only changed `.jsonl` files into private local state. Removing a registration
keeps records already retained in the Vault and database.

## Distill selected work

Metadata-only is the default:

```powershell
wa distill ses_... --using codex
```

Allow selected content to a remote runtime explicitly:

```powershell
wa distill ses_... --using codex --allow-remote-content
wa distill ses_... --using claude --allow-remote-content
```

Select the newest captured sessions that have not been distilled without
copying IDs by hand:

```powershell
wa distill --pending --limit 3 --using codex --allow-remote-content
```

`--pending` defaults to three sessions and accepts a limit from 1 through 20.
The selected IDs are printed before curator execution. It never includes
metadata-only or already-distilled sessions.

Use a local Ollama model:

```powershell
ollama pull qwen3:8b
wa runtimes
wa distill ses_... `
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
wa import C:\path\to\record.json
```

## Import old repository Almanacs

Existing repository Wikis are copied into an isolated review namespace. The
source repository is never modified:

```powershell
wa migrate-almanac C:\path\to\old-repository
```

Only UTF-8 Markdown below `.almanac/pages` is copied. Non-Markdown files are
ignored, symlinks are rejected, and the total import is limited to 50 MB.

## Privacy and backup

Two locations contain private data:

- the configured Markdown Vault;
- `%LOCALAPPDATA%\WorkAlmanac`, which contains SQLite state, retained event
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
wa doctor --runtimes
wa auto status
```

Run one safe incremental retry:

```powershell
wa sync --from codex --from claude --include-content
```

Reinstall automatic sync:

```powershell
wa auto remove
wa auto install --every 5 --from codex --from claude --include-content
```

The Markdown Vault remains the durable source of truth. Search indexes,
operation receipts, and generated navigation can be rebuilt from the Vault and
retained sessions.
