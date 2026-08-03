# Slice 181 — Localized Wiki representations

## Intent

Represent one durable Wiki topic in its original language and, when available,
as a derived Korean or English translation without creating duplicate graph
nodes, routes, backlinks, or source records.

## Shape

- Add typed `Locale` and `TranslationStatus` models.
- Keep the canonical identity at its existing durable Markdown path.
- Store only non-original representations under
  `translations/<locale>/<canonical path>`.
- Record `translation_of`, `language`, and `source_digest` on translated files.
- Resolve a requested locale to a current translation, stale translation, or
  the canonical original with an explicit status.
- Exclude translation files from the Wiki catalog and graph by construction.
- Extend viewer page contracts with localized titles and representation state.

## Verification

- Original-language requests read the canonical page.
- Current, stale, missing, invalid, and path-escape translation cases are
  covered.
- Backlinks and graph node counts remain canonical.
