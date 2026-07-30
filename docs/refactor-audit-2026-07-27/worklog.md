# Worklog

## 2026-07-27

### Initial product reframe

The requested product is not a larger CodeAlmanac. It is a different center of
gravity:

- CodeAlmanac centers one repository and derives a wiki about that codebase.
- Work Almanac centers one person and derives durable memory from activity
  across repositories, hosts, shells, agents, and manual notes.

The useful inherited concepts appear to be:

- local-first Markdown as durable human-readable knowledge;
- SQLite as disposable/derived query state;
- source evidence and backlinks;
- AI-assisted ingest and garden operations;
- provider seams for Codex and Claude;
- searchable viewer and job observability.

The suspect inherited assumptions are:

- every durable page belongs under a registered repository;
- a transcript can be assigned to exactly one repository;
- source paths and Git commits are the dominant evidence types;
- macOS `launchd` is the automation model;
- the wiki page is the first stored representation of work;
- the current lifecycle names (`build`, `ingest`, `garden`) describe the new
  product honestly.

### Next inspection

- Map composition root, repository selection, transcript discovery, sync,
  source normalization, run queue, wiki writes, and index projections.
- Separate reusable mechanisms from repository-wiki product policy.
- Test a target vocabulary around event, session, artifact, memory, and source.

### Final synthesis

Three independent reviews agreed that this is an aggregate-root change, not an
optional-repository feature. The final recommendation adopts:

- a person-owned `Vault`;
- stable `Host`, `Environment`, `Workspace`, and optional `Project` identities;
- retention-bound normalized events with per-collector cursors;
- retained, editable work sessions between raw evidence and durable knowledge;
- one Markdown writer and many collectors;
- explicit model-content access classes;
- foreground curator execution before reintroducing detached job machinery;
- a read surface organized around sessions and durable knowledge, not raw
  surveillance or job status.

The reviews disagreed mainly on how much existing execution/viewer machinery to
keep. The synthesis keeps their valuable mechanisms but removes them from the
first walking slice. This avoids both a rewrite that discards proven code and a
rename that preserves the wrong product center.
