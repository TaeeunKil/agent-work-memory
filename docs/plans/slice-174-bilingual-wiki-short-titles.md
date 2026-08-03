# Slice 174 - Bilingual Wiki short titles

## Intent

Give every durable Wiki page concise Korean and English graph titles, use the
appropriate short title as the graph label without replacing the canonical H1,
and make future distillation maintain both fields automatically.

## Shape

```python
page = wiki.read_page(path)
page.short_title_ko
page.short_title_en

node = viewer.graph_node(page)
node.title  # canonical H1 for details
node.label  # language-appropriate concise graph label
```

The durable Markdown frontmatter is the source of truth:

```yaml
short_title_ko: 간결한 한국어 제목
short_title_en: Concise English title
```

Graph-label selection follows the canonical title language. A title containing
Hangul prefers `short_title_ko`; other titles prefer `short_title_en`. Missing
or blank values fall back to the other short title and then the canonical H1.
Both localized values remain in the graph response as a clean seam for a later
explicit language switch.

## Work

1. Extend `WikiPage` and its frontmatter reader with the two optional titles.
2. Extend graph nodes with `label`, `short_title_ko`, and `short_title_en` while
   preserving the canonical `title`.
3. Render Cytoscape node text from `label` and keep detail/search behavior on
   the canonical title.
4. Add the bilingual-title contract to both curator instructions and the
   dynamic distillation prompt.
5. Backfill every current non-index durable page by changing only its YAML
   frontmatter, then refresh generated Wiki indexes.
6. Cover parsing, fallback selection, graph serialization, and curator prompt
   behavior with isolated tests.

## Safety

- Tests use isolated temporary Vaults and never access the configured Vault.
- The one-time backfill resolves every target beneath the configured Vault and
  rejects missing, duplicate, or unexpected paths before writing.
- Existing bodies, H1 headings, sources, tags, and unknown frontmatter keys are
  preserved.
- No generated index, session record, runtime state, or Git metadata is edited
  by the backfill.

## Gates

```powershell
uv run pytest tests/test_agentworkmemory*.py
uv run ruff check src/agentworkmemory tests/test_agentworkmemory*.py
node --check src/agentworkmemory/viewer/assets/app.js
```
