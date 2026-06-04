# Frontend-Assumed Backend Gaps

This document lists backend capabilities the Banner Studio frontend assumes or benefits from, but which are currently unavailable, intentionally fail-closed, incomplete for the browser demo, or only represented as local/static UI presets.

Created after executing `docs/plans/2026-06-03-frontend-real-data-integration.md`.

## Confirmed backend gaps / fail-closed areas

### 1. Generation run runtime DB failure

Current observation:
- `POST /api/v1/campaigns/{campaign_id}/generation-runs` can return `500` in the running uvicorn/Supabase local environment.
- The observed error was an insert into `generation_events` with `output_summary = null` violating a not-null DB constraint.
- In-process tests/smoke can pass, so this appears to be an environment/schema/default alignment gap that must be fixed before browser generation can be considered green.

Frontend assumption:
- Generate stage expects backend generation runs/events to succeed and provide progress.

Current frontend behavior after integration:
- Shows the backend error and does not auto-advance as if generated.

Backend needed:
- Align deterministic generation event payloads with Supabase schema constraints.
- Add regression coverage that uses the real migration-shaped schema, not only in-memory fakes.

### 2. Real revision creation and selected revision availability

Current observation:
- Generation/revision endpoints exist, but browser/local demo often has no selected revision after generation fails.
- Canvas, schedule, publish, and performance proposal flows assume a selected revision.

Frontend assumption:
- Canvas can load layout variants/segment variants from backend revisions.
- Schedule can target selected revision.
- Optimization proposal can use source_revision_id.

Current frontend behavior:
- Shows local/prototype variant data when backend revisions are unavailable.

Backend needed:
- Ensure successful generation creates campaign revisions, layout variants, segment variants, selected revision/variant pointers, preview/audit artifacts, and campaign status transitions consistently.

### 3. Preview and audit availability in browser/local mode

Current observation:
- `GET /api/v1/campaigns/{campaign_id}/preview` and `/audit-report` exist, but fail closed when no revision/artifact exists or Supabase/RLS bearer context is unavailable.

Frontend assumption:
- Generate/Canvas can display generated HTML preview/audit results.

Current frontend behavior:
- Shows fail-closed notices and keeps local visual preview fallback.

Backend needed:
- Provide deterministic local preview/audit rows after generation.
- Confirm bearer/demo auth path works from static frontend without secrets.

### 4. Approval service default unavailable

Current observation:
- Approval/comment/refinement endpoints exist, but default configured approval/comment services can return `503` unavailable in local/default runtime.
- Approval request can also fail if no reviewable revision exists.

Frontend assumption:
- Canvas approval panel can represent real backend approvers/status and transition campaign status to `approved` after all reviewers approve.

Current frontend behavior:
- Clearly labels local/prototype approvals and does not pretend they unlock backend schedule/publish.

Backend needed:
- Wire default approval/comment/refinement services to Supabase repositories for local demo.
- Seed or derive reviewer users for demo team.
- Ensure approval thread can be created for generated selected revisions.

### 5. Refinement/regeneration full path

Current observation:
- Refinement request/regenerate routes exist but are often unavailable/fail-closed without revision/approval service availability.

Frontend assumption:
- Canvas comments/refinement prompts can create refinement requests and regenerate a new revision.

Current frontend behavior:
- Shows backend fallback and preserves local/prototype refinement messaging only as labeled preview.

Backend needed:
- End-to-end path: comment/request changes -> refinement request -> regenerate -> new revision -> selected/superseded state -> UI-refreshable revision list.

### 6. Scheduling happy path

Current observation:
- Schedule endpoints exist but require approved campaign and selected revision.
- In current demo, schedule commonly returns `409` because campaign is not backend-approved and/or has no selected revision.

Frontend assumption:
- Programar can create a schedule after approval.

Current frontend behavior:
- Shows prerequisite blockers and backend 409 details; does not mark scheduled unless backend accepts.

Backend needed:
- Make demo flow capable of creating approved campaigns with selected revision.
- Verify schedule create/update/cancel against real Supabase schema and team scoping.

### 7. Shopify publish adapter

Current observation:
- Publish endpoints exist but default publisher intentionally returns `503` because no injected Shopify client adapter is wired and it refuses to read/print Shopify secrets.

Frontend assumption:
- Publicar ahora eventually publishes controlled Liquid/theme/metafield config to Shopify.

Current frontend behavior:
- Clearly fail-closed; does not mark published unless backend accepts.

Backend needed:
- Safe request-scoped/decrypted Shopify client adapter.
- Store/theme credential resolution from secure storage, not frontend headers.
- Theme file install + metafield config publish/unpublish happy path.
- Guardrails: scheduled status required, no search placement unless implemented, rollback/idempotency.

### 8. Live Shopify resource sync

Current observation:
- Store/resource endpoints read Supabase cache or seeded deterministic resources.
- Live Shopify sync is documented as non-MVP/manual.

Frontend assumption:
- Placement/catalog data can represent real Shopify pages/products/collections.

Current frontend behavior:
- Shows cached/seeded backend resources, not live sync.

Backend needed:
- A sync/import endpoint/job for Shopify resources with safe credentials, idempotent cache updates, and stale-data labeling.

### 9. Model bank list/create endpoint

Current observation:
- Frontend has `MODELS` and a local model generation UX.
- Backend art direction can store `model_key`/`custom_model`, but no dedicated endpoint lists or creates model-bank assets.

Frontend assumption:
- The model bank can become real brand/model assets.

Current frontend behavior:
- Labels model bank as local UI presets.

Backend needed:
- Model/persona asset list/create/update endpoints, storage upload integration, generated model metadata, team/brand scoping.

### 10. Hero style/grid option registries

Current observation:
- Frontend has static `HERO_STYLES` and `GRID_OPTS`.
- Backend stores art direction/layout JSON but does not expose style/grid option registries.

Frontend assumption:
- Style/grid choices could be backend-managed or brand-specific.

Current frontend behavior:
- Labels them local UI presets.

Backend needed:
- Optional registry endpoints for art style presets and layout/grid presets, scoped by team/brand/store.

### 11. Evolutionary memory / learning history endpoint

Current observation:
- Backend performance response includes insights/proposals, but no direct endpoint matching the frontend `MEMORY` history cards.

Frontend assumption:
- “Memoria evolutiva” can show historical learnings across campaigns.

Current frontend behavior:
- Uses backend insights/proposals if available; otherwise fallback MEMORY is labeled demo.

Backend needed:
- Campaign/team learning memory endpoint aggregating prior performance/proposal outcomes with provenance labels.

### 12. Live analytics ingestion

Current observation:
- Performance metrics are manual/mock/seed/agent unless explicitly live.

Frontend assumption:
- Dashboard can eventually show live Shopify analytics.

Current frontend behavior:
- Keeps non-live label visible and never claims live unless backend says `live_analytics: true`.

Backend needed:
- Live analytics ingestion path, provenance, source labeling, privacy/team scoping, and scheduled snapshots.

### 13. Brand import UI helper parity

Current observation:
- Backend documents `POST /api/v1/brands/import`.
- Static frontend BrandAPI originally exposed list/get/put; import UI/helper parity may still be incomplete depending on desired UI.

Frontend assumption:
- Brand Context could import Markdown/brand files.

Backend needed:
- Backend has Markdown import; frontend helper/UI may need to be added later if product wants it.

## Summary for team discussion

Frontend is now wired to show real backend data wherever the current backend is usable, and visibly labels fallback/fail-closed paths. The main backend work needed for a real end-to-end demo is:

1. Fix generation events/revision creation in real local Supabase runtime.
2. Wire approvals/comments/refinement to Supabase by default.
3. Make schedule happy path reachable from backend-approved selected revisions.
4. Wire safe Shopify publisher adapter for real publish/unpublish.
5. Add optional backend registries for model/style/grid/memory/live-sync/live-analytics where the UI currently has static assumptions.
