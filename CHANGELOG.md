# Changelog

## 0.1.0 - Unreleased

### Added

- Agent Work Memory (AWM), a private local memory and Markdown Wiki for work
  performed with Codex, Claude, remote SSH hosts, and imported agent records.
- The `awm` and `agent-work-memory` commands.
- Windows schedules named `AWM Sync` and `AWM Auto Distill`.
- Linux systemd user timers named `awm-sync.timer` and `awm-auto-distill.timer`
  for `awm auto` and `awm auto-distill`.
- Durable Wiki Markdown normalization that collapses stacked/CRLF frontmatter
  blocks left by repeated distill merges.

### Changed

- The active product package is now `agentworkmemory`.
- The default Windows state directory is `%LOCALAPPDATA%\AgentWorkMemory`.
- The local viewer, generated Wiki navigation, documentation, and repository
  metadata now use Agent Work Memory terminology.
- Documentation now describes Linux systemd user timers alongside Windows Task
  Scheduler instead of saying scheduled commands are Linux-manual-only.
- Distill frontmatter preservation now rewrites a single clean frontmatter
  block instead of restacking curator metadata on corrupt page bodies.

### Historical upstream releases

The entries below describe the upstream CodeAlmanac project retained as
reference source in this fork.

## 0.4.0 - 2026-07-10

### Changed

- Configuration now lives only at `~/.codealmanac/config.toml`.
  Repository-level `almanac/config.toml` is no longer read.
- Sync, Garden, and Update enabled states and intervals are user config keys.
  `codealmanac config set` applies automation changes immediately, while
  `codealmanac config apply` applies direct TOML edits.
- `codealmanac automation install` and `automation uninstall` were removed.
  Use `config set automation.<task>.*`; `automation status` remains available.
