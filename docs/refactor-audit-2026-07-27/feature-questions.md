# Product Questions

## Recommended defaults

| Question | Recommended default |
|---|---|
| Canonical vault host | Current Windows laptop for the MVP; move to a private Linux host only after local capture is reliable. |
| Durable knowledge | Private Git-tracked Markdown. |
| Raw provider records | Remain at their source by default. Do not commit them. |
| Capture ledger | Private local SQLite with per-source cursors and bounded redacted payloads. |
| Curator | Codex first because it is already integrated; Claude remains an alternative. |
| Local model | Input adapter is allowed early; curator adapter is deferred until tool/write quality is proven. |
| Auto-commit | Configurable prompt policy; keep disabled during the first migration slices, then reconsider for unattended distill. |
| Shell capture | Explicit wrapper only, disabled by default. |
| Remote capture | One-way append to one writer over SSH, after the local MVP. |
| Search | FTS5 first. |

## Choices to settle before implementation

1. Final public name and CLI: `WorkAlmanac` / `wa`, `MyAlmanac`, or another
   identity.
2. Whether the vault is strictly work-only or may include broader personal
   context. The recommended first boundary is work-only.
3. Whether the Windows laptop or an existing private Linux server should
   eventually be the always-on vault authority.
4. Default retention for normalized transcript text: metadata only, bounded
   redacted evidence, or full encrypted payload. Recommended: bounded redacted
   evidence, with original records left at the source.
5. Whether daily pages should be generated automatically. Recommended: yes as
   an index/digest, but durable decisions and procedures must also update their
   long-lived subject pages.
