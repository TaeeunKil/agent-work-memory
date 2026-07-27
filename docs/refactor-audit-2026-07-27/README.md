# Work Almanac Refactor Audit

## Goal

Critically audit CodeAlmanac to determine which architecture, features,
boundaries, names, abstractions, dependencies, and workflows should be
preserved, simplified, removed, or redesigned so it can become a local-first
personal memory for work performed across Codex, Claude, local models, Windows,
WSL, Linux, and SSH environments.

## Core questions

- Why does each current subsystem exist?
- Which assumptions are specific to a per-repository codebase wiki?
- What is the smallest clean shape that supports a personal work memory?
- Which complexity is reusable, and which is accidental or product-specific?
- How should raw activity, work sessions, durable knowledge, and derived search
  state be separated?
- Where should agent/provider and host/environment differences terminate?

## Non-goals

- Do not modify production code.
- Do not preserve the current architecture by default.
- Do not build capture integrations before agreeing on the event and privacy
  boundaries.
- Do not turn raw transcripts and shell history into permanent wiki prose.

## Success criteria

- The current architecture and its product assumptions are mapped.
- Major boundaries are judged as keep, simplify, delete, or redesign.
- A target architecture and product vocabulary are defined.
- A phased roadmap starts with a useful, privacy-safe MVP.

## Executive verdict

Do not expand CodeAlmanac by making `repository_id` optional. Fork the product
around one person-owned private vault and reuse the current implementation as a
donor.

The central change is:

```text
repository -> transcript sync -> repository wiki

becomes

collector -> retention-bound event -> editable work session
          -> selected curator -> durable Markdown memory -> FTS projection
```

Preserve the composition-root and ports/adapters discipline, Markdown,
citations, FTS5, typed Codex/Claude parsers, direct agent editing, and the
useful parts of run observability. Redesign repository ownership, exact-cwd
matching, global sync watermarks, provider enums, transcript rendering,
launchd-only automation, and repo-scoped jobs/viewer. Freeze telemetry,
self-update, topic-DAG breadth, arbitrary shell collection, SSH transport,
vector search, and local-curator adapters until the core walking slice works.

The MVP should be one Windows-hosted vault, Windows/WSL identity, manual notes,
opt-in Codex/Claude collection, user-correctable sessions, explicit foreground
distillation, Markdown/FTS search, and no background surveillance.

## Documents

- [Active implementation plan](../workalmanac-implementation-plan.md)
- [Worklog](worklog.md)
- [Source map](source-map.md)
- [Major findings](smells.md)
- [Product questions](feature-questions.md)
- [Research notes](research-notes.md)
- [Target architecture](target-architecture.md)
- [Refactor roadmap](refactor-roadmap.md)
- `reports/` contains independent critiques.
