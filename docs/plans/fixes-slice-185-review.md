# Slice 185 review fixes

## Findings

1. The Microsoft Store package is named ChatGPT even though Codex is available
   inside it; calling it the Codex Windows app made the winget result confusing.
2. The first draft linked to an obsolete Windows documentation path.
3. The contributor and "not required" sections described Node.js and npm too
   broadly even though the optional Claude Code path uses both.

## Fixes

1. Name the installed product as the ChatGPT desktop app with Codex.
2. Link to the live desktop quickstart and authentication pages from the
   current OpenAI Codex manual.
3. Scope the no-npm statement to AWM itself and distinguish Claude Code's npm
   installation from the repository's Node-only syntax gate.

## Verification

- All four winget package identifiers resolved successfully.
- A non-editable AWM installation in an isolated uv tool directory completed
  and its `awm --help` entry point ran.
- README reference links have no missing or unused definitions.
