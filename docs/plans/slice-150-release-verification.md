# Slice 150: Work Almanac v1 release verification

Status: complete.

## Outcome

Prove that the development branch can be installed on Windows and used as the
owner's private daily Work Almanac without relying on the repository virtual
environment.

## Scope

- Run the complete Python and static validation gates.
- Build wheel and source distributions.
- Inspect the wheel for Work Almanac prompts and viewer assets.
- Install the branch as an editable uv tool.
- Initialize the owner's private Markdown Vault.
- Retain existing Codex and Claude session content with explicit local consent.
- Install five-minute Windows automatic synchronization.
- Verify diagnostics, scheduler status, sessions, search, and a loopback viewer
  health request.
- Record the completed verification and any explicitly deferred extensions.

## Out of scope

- Sending transcript bodies to a remote curator.
- Pulling or running a large Ollama model automatically.
- Exposing the viewer outside `127.0.0.1`.
- Merging the development branch into `main`.
- Publishing a PyPI release.

## Safety boundaries

- Real transcript bodies remain in `%LOCALAPPDATA%\WorkAlmanac` and the selected
  private Vault.
- Automatic sync performs collection and indexing only.
- No distillation is run during release verification.
- Validation output must not print transcript bodies.
- `main` and upstream remotes remain unchanged.

## Verification sequence

1. Build distributions from the committed development branch.
2. Install `wa` from this checkout with `uv tool install --editable . --force`.
3. Run `wa setup C:\Users\user\Documents\WorkAlmanacVault
   --include-content --auto --every 5`.
4. Run `wa doctor`, `wa auto status`, and a bounded session/search check.
5. Start the viewer on an unused loopback port, request its health endpoint,
   and stop it.
6. Mark Slice 150 complete, run final gates, commit, and push only
   `codex/workalmanac`.

## Read before execution

- `CLAUDE.md`
- `MANUAL.md`
- `docs/workalmanac-v1-completion-plan.md`
- `docs/workalmanac-user-guide.md`

## Rollback

- `wa auto remove` removes the scheduled task.
- The uv tool can be replaced or uninstalled independently of repository
  history.
- The Vault is ordinary Markdown and remains readable without the CLI.

## Result

- Wheel and sdist built successfully with all `workalmanac` resources.
- The user-level editable tool exposes `wa` and `workalmanac`.
- The private Vault and five-minute scheduled sync are installed.
- Real-data runtime diagnostics, indexed search, and loopback viewer checks
  passed without exposing transcript content.
