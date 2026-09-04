# Slice 196: Publish successful automatic distillation

## Goal

Make the automatic distillation workflow publish durable Wiki changes to the
configured Vault Git repository immediately after a successful batch, while
keeping translation and publication outside the curator workspace.

## Scope

- Wire the existing Vault repository workflow into automatic distillation when
  the configured Vault is already a Git repository.
- Publish only batches that changed durable Wiki files, using the existing
  coordinated Vault sync path.
- Avoid rebuilding derived Wiki/search views during automatic publication.
- Add focused workflow coverage for automatic publication.

## Verification

- Run the focused auto-distillation and Vault repository tests.
- Run the full test suite and lint/type-independent repository checks already
  used by the project.
- Verify the installed runtime and live Vault remain clean after publication.
