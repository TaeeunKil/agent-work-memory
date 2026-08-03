# Slice 174 review fixes

## Review outcome

The first pass correctly added the bilingual title contract, but review found
two concrete integration issues before final verification.

## Findings and fixes

1. **Fix - Windows frontmatter validation rejected CRLF files.**
   `VaultService.validate_markdown_page` inspected decoded bytes with LF-only
   delimiters. The configured Vault uses CRLF, so valid frontmatter appeared
   absent when the new title invariant ran. Frontmatter matching now accepts LF
   and CRLF, with an isolated regression test that writes CRLF bytes.
2. **Restructure - frontmatter syntax was duplicated across Wiki and Vault
   services.** The shared fence parser now lives in
   `services/frontmatter.py`; the Wiki reader, viewer renderer, and Vault
   validator consume that single syntax boundary.
3. **Fix - curator test doubles emitted pages that violated the new contract.**
   Viewer, distillation, and Ollama fixtures now emit both short titles so the
   tests represent valid future curator output.

## Residual risk

Title quality is editorial rather than mechanically provable. The current
89-page backfill was length-checked and path-complete, while future runs rely on
the curator contract plus non-empty field validation. An explicit graph
language selector remains additive because both localized values are already in
the graph response.
