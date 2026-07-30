# Slice 169 — Git-backed private Vault

## Intent

Keep the Agent Work Memory application shareable while allowing a person's
complete Markdown Vault, including retained session evidence, to live in a
separate private Git repository that can be carried between machines.

The current user's existing Vault will become the working tree for the private
`TaeeunKil/taeeun-work-memory` repository. Runtime SQLite state, locks, logs,
and schedules remain outside the Vault under the platform state directory.

## Architectural fit

Git is not a Vault file-format concern. The feature therefore adds:

- a repository service that owns the version-control verbs and typed results;
- a service-owned adapter port;
- a Git integration that owns subprocess execution and error redaction;
- a workflow that coordinates repository changes with Vault configuration,
  Wiki catalog refresh, and search refresh;
- a `awm vault` CLI surface that only adapts arguments and prints results.

```python
status = awm.vault_repository.status()
awm.vault_repository.connect(repository, destination)
awm.vault_repository.publish(repository)
awm.vault_repository.pull()
awm.vault_repository.push(message)
awm.vault_repository.sync(message)
```

`sync` records local Vault changes, rebases on the private remote, and pushes
without force. A conflict stops with Git's normal recovery state and a clear
error rather than discarding either copy.

## User surface

```text
awm vault connect <repository> <path>
awm vault publish <repository>
awm vault status
awm vault pull
awm vault push [--message TEXT]
awm vault sync [--message TEXT]
```

- `connect` clones an existing Vault repository into an empty/nonexistent path,
  configures it as AWM's Vault, creates any missing standard directories, then
  refreshes generated Wiki navigation and local search.
- `publish` initializes the currently configured Vault as a `main` Git
  repository, attaches the remote, records every Vault file, and pushes it.
- `pull` requires a clean worktree and fast-forwards/rebases from the remote,
  then refreshes Wiki navigation and search.
- `push` records all current Vault changes and pushes them.
- `sync` records all current Vault changes, pulls with rebase, then pushes.
- `status` reports branch, remote, and whether local changes exist.

All commands operate only on the configured Vault root. They do not copy the
runtime database into Git.

## Safety

- Git commands use argument arrays and never a shell.
- Windows child processes are hidden.
- Repository credentials embedded in URLs are redacted from surfaced errors.
- Clone refuses a nonempty destination.
- Publish safely resumes an interrupted first push when the existing `origin`
  matches, and refuses a remote mismatch.
- Pull never proceeds over uncommitted changes.
- No force push, reset, clean, or automatic conflict resolution.
- Tests use temporary Vaults and fake adapters only.

## Acceptance

- Existing initialization and setup behavior remains compatible.
- A fake repository adapter proves connect/publish/pull/push/sync sequencing.
- The concrete Git adapter is covered with temporary local bare repositories.
- CLI parsing and output cover every `awm vault` verb.
- Wiki/search refresh after connected or pulled repository content.
- The complete real Vault is committed and pushed to a verified private GitHub
  repository, and the application source repository remains separate.
