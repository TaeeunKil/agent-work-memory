# Slice 158 review fixes

## Findings and fixes

- Project inspector layout: opening the right inspector reduced the workspace
  width enough for the Projects heading and supporting copy to overlap. Stack
  the view header while the inspector is open.
- Activity isolation: viewer-triggered Wiki builds initially treated activity
  ledger writes as mandatory. Make activity recording best-effort so a local
  logging permission error cannot block durable knowledge creation.
- Content permission: a bulk Wiki build must not silently inherit permission.
  Require an explicit content-access selection before starting a batch.

No further correctness or architecture findings remained after these fixes.
