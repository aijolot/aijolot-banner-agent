# Frontend hardcoded data inventory

This inventory tracks which visible Banner Studio data is now backed by `/api/v1` and which values remain static because they are UI metadata, visual renderer defaults, or explicit fail-closed fallback data.

Scope: static React prototype under `frontend/` on branch `feature/frontend-real-data-integration` after the frontend real-data integration phases.

## Rules

- Backend-backed data is the source of truth when a UUID campaign and `/api/v1` demo auth context are available.
- Static constants may remain only as UI labels/presets, visual mock copy, or visibly labeled fallback/demo data.
- Local/non-UUID campaign ids are prototype-only and cannot be treated as durable backend state.
- Backend failures must be surfaced through notices/badges/save state; the UI must not silently swap to static data as if it were real.
- Performance data is non-live/manual/mock/seed/agent unless the backend explicitly returns `live_analytics: true`.
- Schedule/publish and unavailable review/generation-adjacent flows are fail-closed: controls may call the backend, but rejected responses must leave local scheduled/published state unchanged.

## Backend-backed frontend data

| Area | Frontend files | Backend source | Current behavior |
| --- | --- | --- | --- |
| Campaign list and active campaign | `Shell.jsx`, `App.jsx`, `lib.jsx` | `GET/POST/PATCH /api/v1/campaigns`, `POST /api/v1/campaigns/intake` | Banner Studio lists backend campaigns first. Intake returns a UUID campaign and chip edits patch backend state. Demo/prototype campaign cards are labeled fallback when used. |
| Brief extraction and chip persistence | `BriefStage.jsx`, `components/Chatbox.jsx`, `components/CampaignChips.jsx` | `POST /api/v1/campaigns/intake`, `PATCH /api/v1/campaigns/{id}` | Chat streams backend intake events. Local rule extraction exists only as offline fallback. Chip save state exposes saving/saved/save-failed. |
| Brand context | `BrandContextView.jsx`, `data.jsx` (`BrandAPI`) | `GET/PUT /api/v1/brands` | Brand list/get/save uses backend when reachable. `BRAND_SEEDS` are offline fallback only. Font preview text remains UI metadata. |
| Stores, resources, and placement choices | `PlacementStage.jsx`, `StoreMocks.jsx`, `data.jsx`, `lib.jsx` | `GET /api/v1/stores`, `GET /stores/{id}`, `GET /stores/{id}/shopify/resources`, `GET /stores/{id}/placement-types`, `GET /stores/{id}/placement-types/{key}/targets`, `POST /api/v1/placements/validate`, `POST/GET /api/v1/campaigns/{id}/placement` | Store name/domain, product/collection/page/search resources, placement type keys, validation, save, and load are backend-backed when available. `STORE_PAGES`, `BRANDS`, and `COLLECTIONS` are labeled fallback when backend resources are missing. |
| Catalog snapshot and art direction | `ArtStage.jsx`, `ModelBank.jsx`, `data.jsx`, `lib.jsx` | `POST/GET /api/v1/campaigns/{id}/catalog-snapshot`, `PUT/GET /api/v1/campaigns/{id}/art-direction` | Art stage creates/loads backend catalog snapshots and persists/rehydrates art direction. Product/resource cards prefer backend snapshot data. |
| Generation progress and events | `GenerateStage.jsx`, `lib.jsx` | `POST /api/v1/campaigns/{id}/generation-runs`, `GET /api/v1/campaigns/{id}/generation-runs/latest`, `GET /api/v1/generation-runs/{run_id}`, `GET /api/v1/generation-runs/{run_id}/events` | Progress and StepRail status map backend run/events when generation succeeds. Start/events errors are visible and do not advance as a false success. |
| Preview/audit/revisions attempts | `GenerateStage.jsx`, `CanvasStage.jsx`, `lib.jsx` | `GET /api/v1/campaigns/{id}/preview`, `GET /api/v1/campaigns/{id}/audit-report`, `GET /api/v1/campaigns/{id}/revisions`, `POST /api/v1/campaigns/{id}/variants/{variant_id}/select`, `POST /api/v1/campaigns/{id}/regenerate` | The frontend attempts backend preview/audit/revisions/selection/regenerate. Success is shown as backend state; unavailable local-demo paths are shown as fail-closed/fallback notices. |
| Approval/comment/refinement guardrails | `CanvasStage.jsx`, `CanvasPanels.jsx`, `lib.jsx` | Approval thread/comment/refinement routes exposed by `ReviewApi`/`GenerationApi` | Real backend success is surfaced when available. Missing thread/reviewer/revision context is labeled local/prototype and fail-closed. |
| Schedule and publish | `CanvasStage.jsx`, `CanvasPanels.jsx`, `lib.jsx` | `POST/PATCH/cancel /api/v1/campaigns/{id}/schedule`, `POST /api/v1/campaigns/{id}/publish`, `POST /api/v1/campaigns/{id}/unpublish` | Buttons call backend only under guarded conditions where possible. `409`/`503`/other rejections are shown and do not mark local state as scheduled/published. No live Shopify publishing is claimed. |
| Performance and optimization | `PerformanceStage.jsx`, `data.jsx`, `lib.jsx` | `GET /api/v1/campaigns/{id}/performance`, `POST /api/v1/campaigns/{id}/performance/snapshots`, `POST /api/v1/campaigns/{id}/optimization-proposals` | KPI cards, snapshots, segment/trend data, insights, and proposals render from backend when present. Manual snapshots and proposals call backend. Static metrics/memory are labeled demo/no-live fallback. |

## Static UI metadata that intentionally remains

These values are not backend source-of-truth data and may stay static:

- Navigation labels, stage labels, headings, helper copy, button text, icons, badge colors, and Spanish UI strings.
- Date/month/week labels and animation timing/progress display labels.
- Visual renderer geometry, gradients, placeholder bottle/model shapes, mock browser chrome, and layout scaffolding.
- Required-field labels, chat prompt suggestions, chip labels, and other form affordances.
- Device labels and preview viewport names used to render responsive mockups.
- `PIPELINE` titles and `CODE_LINES` typing animation as display/fallback labels when backend generation events do not provide a specific label.
- `SEGMENTS`, `SEGMENT_ORDER`, and `VARIANTS` as prototype rendering presets unless backend revisions/layout variants are loaded.
- `SCOPE_OPTS` as rule-builder UI labels; backend validation/save remains the authority for accepted placement payloads.

## Remaining fallback/demo constants

| Constant(s) | File | Why it remains | Visibility requirement |
| --- | --- | --- | --- |
| `CAMPAIGN` | `data.jsx` | Initial local/prototype campaign seed for no-backend or non-UUID flows. | Must be labeled prototype/fallback when used instead of a backend UUID. |
| `CATALOG` | `data.jsx` | Product cards for no-backend catalog rendering. | Art stage labels it as fallback/demo when no backend snapshot/resource cache is available. |
| `BRAND`, `BRAND_SEEDS` | `data.jsx` | Offline brand fallback and visual brand defaults. | Brand Context exposes connected/offline status; validation/server errors are not swallowed. |
| `STORE_PAGES` | `data.jsx` | Visual page/slot fallback and mock renderer data. | Placement stage badges pages/slots/resources as `Fallback STORE_PAGES` when backend hydration fails. |
| `BRANDS`, `COLLECTIONS` | `data.jsx` | Fallback filters when backend product vendors/collections are missing. | Placement chips show `vendors backend`/`colecciones backend` or amber fallback labels. |
| `HERO_STYLES`, `MODELS`, `GRID_OPTS` | `data.jsx`, `ModelBank.jsx`, `ArtStage.jsx` | Backend stores selected keys/custom model values but has no style/model-bank/grid list endpoints. | UI must call these local presets, not backend-provided models/styles. |
| `PIPELINE`, `CODE_LINES` | `data.jsx`, `GenerateStage.jsx` | Display labels and typing animation. | Backend run/events are authoritative; generation errors stay visible and do not auto-complete. |
| `APPROVERS_SEED`, `COMMENTS_SEED` | `data.jsx`, `CanvasStage.jsx`, `CanvasPanels.jsx` | Prototype reviewer/comment visuals when approval thread is unavailable. | Canvas labels approval/comments as local/prototype unless backend thread/comment calls succeed. |
| `METRICS`, `SEG_PERF`, `CTR_TREND`, `MEMORY` | `data.jsx`, `PerformanceStage.jsx` | Demo performance visuals when backend performance has no snapshot/trend/insights/proposals. | Must be labeled demo/fallback/no-live; never claim live Shopify analytics. |

## Known backend/API gaps surfaced by the frontend

- No model-bank list/create endpoint matching the prototype model selector; art direction can persist selected metadata only.
- No hero-style/grid preset list endpoint; style/grid choices are local UI presets persisted as keys/layout hints.
- Preview/audit/revision data may be unavailable in local/no-Supabase mode; UI attempts routes and shows fail-closed notices.
- Approval thread/comment/refinement flows depend on real reviewer/revision context and local backend services; static prototype labels local approval state when the backend declines.
- Schedule/publish require backend campaign status/prerequisites and a safe publish adapter; deterministic local demo expects fail-closed before approval/eligible state.
- Performance is seeded/manual/mock/agent in the local demo; live Shopify analytics ingestion is not implemented here.

## Validation record for this inventory

Phase 8 validation commands are recorded in `docs/plans/2026-06-03-frontend-real-data-integration.md`. The final review separately verified that a newly created backend campaign is returned by `GET /api/v1/campaigns` for Shell/Banner Studio visibility. The frontend-backend smoke script exercises intake UUID handoff, placement save/load, catalog/art direction, generation event success or fail-closed behavior, preview/audit/revision attempts, canvas review/schedule/publish guardrails, and non-live performance labels.
