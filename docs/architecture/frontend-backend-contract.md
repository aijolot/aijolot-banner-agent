# Static frontend ↔ FastAPI backend contract

The current frontend in `frontend/` is a static React 18 UMD/Babel prototype. It has no Next.js/Tailwind build step in this branch. The frontend real-data integration connected the visible Banner Studio flow to local FastAPI `/api/v1` APIs through small static adapters while keeping visible fallbacks for prototype-only state and fail-closed backend gaps.

For the static-data audit, see `docs/architecture/frontend-hardcoded-data-inventory.md`.

## Runtime API base

The prototype reads:

```js
window.AIJOLOT_API_BASE || "http://localhost:8000"
```

`frontend/lib.jsx` normalizes this to `window.API_BASE` and exposes:

- `AijolotApi.get/post/put/patch(path, body)`
- `AijolotApi.v1(path)` for `/api/v1` paths

Example override before loading the app:

```html
<script>window.AIJOLOT_API_BASE = "http://localhost:8000";</script>
```

## Auth context

Canonical `/api/v1` callers should send demo auth/team context. The static prototype now centralizes that in `frontend/lib.jsx` through `AIJOLOT_DEMO_AUTH_HEADERS`; every `AijolotApi` request to `/api/v1` includes:

- `X-Aijolot-User-Id`
- `X-Aijolot-Team-Id`
- `X-Aijolot-Store-Id`
- `Authorization: Bearer demo:<user_id>:<team_id>:<store_id>` for endpoints that require the demo bearer form (for example preview access)

Accepted backend forms are documented in `docs/architecture/api-contract.md`:

- `X-Aijolot-User-Id`
- `X-Aijolot-Team-Id`
- optional `X-Aijolot-Store-Id`
- or `Authorization` using bearer format `Bearer demo:<user_id>:<team_id>[:<store_id>]`

The deterministic smoke script supplies these headers itself. Browser demos should verify the static frontend version being served includes/sends demo context before claiming an authenticated end-to-end API flow. Do not put real Gemini/Supabase/Shopify secrets in browser headers.

For a copy/paste-friendly list of frontend API functions, parameters, and payloads, see `docs/architecture/frontend-integration-function-reference.md`.

Demo fixture ids:

```text
team  = 00000000-0000-0000-0000-000000000001
user  = 00000000-0000-0000-0000-000000000601
store = 00000000-0000-0000-0000-000000000101
```

## Adapters exposed on `window`

Defined primarily in `frontend/lib.jsx` and `frontend/data.jsx`. `AijolotApi.v1(path)` normalizes paths so `/api/v1` is appended exactly once, and `AijolotApi.streamIntakeEvents(...)` uses incremental `ReadableStream` parsing for browser UX.

- `CampaignApi`
  - `POST /api/v1/campaigns`
  - `GET /api/v1/campaigns`
  - `GET /api/v1/campaigns/{campaign_id}`
  - `PATCH /api/v1/campaigns/{campaign_id}`
- `StoreApi`
  - `GET /api/v1/stores`
  - `GET /api/v1/stores/{store_id}`
  - `GET /api/v1/stores/{store_id}/shopify/resources`
  - `GET /api/v1/stores/{store_id}/placement-types`
  - `GET /api/v1/stores/{store_id}/placement-types/{placement_type_key}/targets`
- `PlacementApi`
  - `POST /api/v1/placements/validate`
  - `POST /api/v1/campaigns/{campaign_id}/placement`
  - `GET /api/v1/campaigns/{campaign_id}/placement`
  - default seeded store id: `00000000-0000-0000-0000-000000000101`
  - prototype placement mapping uses seeded backend placement keys: `announcement_bar`, `hero_main`, `promo_card`, `collection_header`, `pdp_strip`, `pdp_cross_sell`, `footer_cta`, `search_results_banner`
  - collection/product target handles in the seeded fixture include `fragancias` and `boss-bottled-edp-100ml`
- `CatalogApi`
  - `POST /api/v1/campaigns/{campaign_id}/catalog-snapshot`
  - `GET /api/v1/campaigns/{campaign_id}/catalog-snapshot`
- `ArtDirectionApi`
  - `PUT /api/v1/campaigns/{campaign_id}/art-direction`
  - `GET /api/v1/campaigns/{campaign_id}/art-direction`
- `GenerationApi`
  - `POST /api/v1/campaigns/{campaign_id}/generation-runs`
  - `GET /api/v1/campaigns/{campaign_id}/generation-runs/latest`
  - `GET /api/v1/generation-runs/{run_id}`
  - `GET /api/v1/generation-runs/{run_id}/events`
  - `GET /api/v1/campaigns/{campaign_id}/preview`
  - `GET /api/v1/campaigns/{campaign_id}/audit-report`
  - `GET /api/v1/campaigns/{campaign_id}/revisions`
  - `POST /api/v1/campaigns/{campaign_id}/variants/{variant_id}/select`
  - `POST /api/v1/campaigns/{campaign_id}/regenerate`
- `ReviewApi`
  - canvas approval remains local/labeled until authenticated reviewer UUID and revision context are available in the static prototype
  - approval/comment/refinement helpers are exposed for the canonical backend routes but still display/fail closed when the local approval service is unavailable
  - `POST /api/v1/campaigns/{campaign_id}/schedule`
  - `PATCH /api/v1/campaigns/{campaign_id}/schedule`
  - `POST /api/v1/campaigns/{campaign_id}/schedule/cancel`
  - `POST /api/v1/campaigns/{campaign_id}/publish`
  - `POST /api/v1/campaigns/{campaign_id}/unpublish`
- `PerformanceApi`
  - `GET /api/v1/campaigns/{campaign_id}/performance`
  - `POST /api/v1/campaigns/{campaign_id}/performance/snapshots`
  - `POST /api/v1/campaigns/{campaign_id}/optimization-proposals`
- `BrandAPI`
  - `GET /api/v1/brands`
  - `GET /api/v1/brands/{brand_id}`
  - `PUT /api/v1/brands/{brand_id}`

Campaign intake streaming uses:

- `POST /api/v1/campaigns/intake`
- SSE lines: `data: { "type": "token", "text": ... }` and final `data: { "type": "done", "campaign": ..., "complete": ..., "missing": ... }`

## Prototype flow wiring

- Brand Context loads/saves through `BrandAPI`.
- Banner Studio campaign list loads `GET /api/v1/campaigns`; backend-created UUID campaigns are rendered before any labeled demo/prototype cards.
- Starting/resuming Studio keeps the active campaign in App state. Durable stage APIs require a UUID campaign id; non-UUID local ids stay prototype-only and visibly labeled.
- Brief chat streams from `/api/v1/campaigns/intake` and stores the returned backend UUID campaign object in authenticated `/api/v1` no-Supabase/Supabase flows.
- Edited brief chips persist with `PATCH /api/v1/campaigns/{campaign_id}` when a backend campaign id/context is usable; save failures show inline save-failed state/notice.
- Placement is selected before intake; placement choices hydrate from backend store/resources/placement types, `POST /api/v1/placements/validate` runs before continuing, and once a backend campaign exists the adapter saves/loads placement.
- Art stage creates/loads a backend catalog snapshot and persists/rehydrates art direction before generation. Model/style lists remain local UI presets because the backend only stores selected metadata.
- Generation starts a backend generation run when the campaign id is a UUID and auth context is accepted. StepRail/progress maps returned run/events; start/event failures stay visible and do not auto-advance to Canvas as a false success.
- Preview, audit, revision list, variant selection, and regenerate/refinement requests are attempted through backend routes. Available backend results are rendered; unavailable local-demo paths are shown as fail-closed.
- Canvas approval/comment controls call the exposed backend helpers when a thread/revision/reviewer context can be resolved. Otherwise reviewer/comment state is explicitly local/prototype.
- Schedule/publish controls call backend endpoints where possible. Backend rejections are shown and do not silently advance local scheduled/published state.
- Performance stage loads backend snapshots/insights/proposals, can post a manual non-live snapshot, and can submit a V2 optimization proposal when a backend revision id exists.

## Current real-data integration matrix

| Frontend area | Backend-backed when available | Static/fallback still allowed |
| --- | --- | --- |
| Shell campaign list | Campaign list/get/create/intake/PATCH data. Created campaigns should appear after refresh. | Demo cards only under fallback/prototype labeling. |
| Brief | Intake stream and chip PATCH save state. | Local extractor only when backend is unreachable and labeled as offline/prototype. |
| Brand context | Brand list/get/put. | `BRAND_SEEDS`, font previews, and copy examples as offline/UI metadata. |
| Placement/store | Store summaries, Shopify resource cache, placement types/targets, validate/save/get. | `STORE_PAGES`, `BRANDS`, `COLLECTIONS`, visual mock page copy as labeled fallback/UI renderer data. |
| Catalog/art | Catalog snapshot create/get and art-direction put/get. | `CATALOG` fallback cards plus `HERO_STYLES`, `MODELS`, `GRID_OPTS` as local presets. |
| Generation | Generation run/latest/get/events; events are progress source. | Pipeline/code animation as labels only; generation errors are fail-closed. |
| Canvas/review | Revisions, select variant, regenerate, approval thread/comment calls when backend accepts them. | Local approvers/comments/segments/variants only when visibly marked prototype/fallback. |
| Schedule/publish | Schedule/publish/unpublish calls with backend prerequisites. | No fake success; unavailable states remain fail-closed. |
| Performance | Performance get, manual snapshots, optimization proposals, backend source labels. | `METRICS`, `SEG_PERF`, `CTR_TREND`, `MEMORY` as demo/no-live fallback only. |

## Fallback and label rules

Fallbacks are allowed only when visible/labeled:

- Backend unreachable for campaigns: Shell shows a backend error and any demo cards are fallback/prototype, not the only implied source of truth.
- Backend unreachable for brands: Brand Context shows offline/mock state.
- Local non-UUID campaign ids are prototype-only. UUID-typed backend stage APIs cannot persist placement/art/generation/schedule/publish for those ids; adapters show amber fallback notices.
- HTTP validation/status errors from backend are surfaced rather than silently swallowed for brand CRUD, brief chip persistence, placement validation/save, art-direction save, generation, review, schedule/publish, and performance actions.
- Placement/store/catalog/product static data is allowed only as visible fallback when backend resources/snapshots are unavailable.
- Model/style/grid presets are local UI metadata because no list endpoints exist; persisted selected art-direction values may still be backend-backed.
- Generation progress must not be claimed successful from static animation alone; backend run/event failure is a visible fail-closed state.
- Schedule/publish backend errors show amber notices and keep local state unchanged unless an explicit labeled fallback is used.
- Performance metrics shown in the frontend are manual/mock/seed/agent unless explicitly marked live; do not present them as live Shopify analytics.

## Manual local browser demo

Terminal 1:

```bash
cd backend
. .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Terminal 2, from repo root:

```bash
python3 -m http.server 5500 --directory frontend
```

Browser:

1. Open `http://localhost:5500`.
2. Open backend API docs at `http://localhost:8000/docs` and verify `/health` plus `/api/v1` routes are present.
3. Brand Context:
   - navigate to Brand,
   - verify connected/offline status is truthfully displayed,
   - edit a safe field and save only if auth/context is accepted.
4. Studio flow:
   - create/resume a campaign,
   - choose placement,
   - enter a campaign brief in chat,
   - verify structured chips populate and edits persist or fallback is labeled,
   - advance to Art,
   - select background/model/fold and assemble,
   - verify art save notice,
   - verify generation progress displays,
   - review canvas and approvals,
   - schedule/publish only after backend status allows it,
   - verify controls stay locked until approval and backend/fallback status is visible.

For deterministic non-browser verification, prefer:

```bash
python3 scripts/reset-demo-data.py --local-only
python3 scripts/smoke-demo-flow.py
```

For frontend-facing endpoint wiring against a running backend, use:

```bash
node scripts/smoke-frontend-backend-connection.mjs
```

This script uses the same `/api/v1` base/auth/path-normalization rules as the static frontend and verifies intake streaming, UUID campaign handoff, placement, catalog/art direction, generation success, generation events/KG context, preview/audit/revision consistency, fail-closed schedule/publish, and non-live performance labels. If persistence is configured and revisions exist, preview HTML and audit report must also exist; without persistence, preview/audit/revisions must fail closed rather than returning inconsistent partial state. It also exercises the newly-wired stage interactions — variant selection, regenerate/refinement, approval-thread request/comment/approve, performance snapshot, and the V2 optimization proposal — accepting either backend success or a fail-closed `503`/`404`/`409`/`422` as correct for optional persistence/approval/publish paths in the deterministic local demo.

For browser-free UI regression confidence, use:

```bash
node scripts/smoke-frontend-ui.mjs
```

This is a source-level smoke (no browser, no network). It asserts the static frontend still contains demo-critical labels and guardrails for resume/create routing, `/api/v1` demo auth/path normalization, backend/fallback campaign labels, intake fallback, placement validation, generation fail-closed states, backend creative vs local canvas fallback, approval/local-prototype labels, schedule/publish guardrails, dry-run Shopify labels, and non-live performance labels.

For the final showcase checklist and command sequence, see `docs/demo/mvp-showcase-runbook.md`.

## Provider truth table

| Area | MVP default | Provider-backed mode | Frontend/demo label rule |
| --- | --- | --- | --- |
| Agent skills | Deterministic local skill pipeline/fallback for smoke. | ADK/Gemini orchestration only when backend is intentionally configured. | Do not claim live model generation unless generation events/artifacts prove it. |
| Image/art provider | Fake/deterministic artifacts or local fallback. | Gemini/image provider if configured outside the smoke path. | Fallback art must stay visibly local/prototype. |
| KG/research | Static KG/best-practices retrieval is sufficient. | Vector/pgvector KG when Supabase/vector seed is configured and event output proves it. | Show static/vector provenance through generation events, not a direct frontend KG query. |
| Persistence | Local fallback/TestClient for deterministic smoke; fail-closed for persistence-only browser routes. | Local Supabase with migrations/seed. | If revisions exist, preview/audit must exist; if not configured, UI shows fail-closed/fallback. |
| Shopify | Dry-run/fail-closed publisher. | Live test-store mutation only with explicit safe config and manual rollback. | Default publish label is dry-run/no live mutation or fail-closed. |
| Performance | Manual/mock/seed/agent non-live metrics. | Live analytics only if separately implemented/configured. | Always show `no-live` unless live analytics are verified. |

## Newly-wired stage interactions

These interactions previously held local-only prototype state and are now wired to their real `/api/v1` calls through the `{ ok, fallback, reason, data }` adapter envelope. Each keeps its existing visual but surfaces an honest amber badge when the backend declines (e.g. `503`/`404`/`422` in the local no-Supabase demo) and a green badge only on a real backend success — never false green.

- **Placement validation** (`frontend/PlacementStage.jsx`): "Continuar al brief" calls `PlacementApi.validate(payloadFromPrototype(...))` (stateless, no campaign UUID needed) before advancing. A green "Ubicación validada por el backend" badge shows on success; a `422` shows an amber "inválida" badge and still advances with the local choice.
- **Variant selection** (`frontend/CanvasStage.jsx`): on mount, `GenerationApi.latestRevision(campaign)` resolves real `layout_variants` (`A|B|C`) and audience `variants` (`segment_key`) UUIDs. Switching layout/segment tabs calls `GenerationApi.selectVariant(campaign, variantId)` when a UUID resolves; local tab switch always happens.
- **Approval + comments** (`frontend/CanvasStage.jsx`, `ReviewApi`): `ReviewApi.ensureThread` lazily gets/creates the approval thread (`GET approval` then `POST approval/request`). Approve/request-changes call `approveThread`/`requestChanges` with the demo reviewer UUID; comment pins call `addComment`/`resolveCommentSafe`. All fail closed visibly — reviewer-identity UI remains prototype-labeled.
- **Refinement loop** (`frontend/CanvasStage.jsx`): "Refinar con el agente" keeps the local shimmer/heuristic visual but fires `GenerationApi.regenerate(campaign, { prompt, source_revision_id })`; the success message appends " (local, sin backend)" on fallback and reloads the latest revision on success.
- **Performance snapshot** (`frontend/PerformanceStage.jsx`): "Registrar snapshot" calls `PerformanceApi.snapshot(campaign, { source: "manual", ... })` and reflects the returned `data_source_label`; clearly labeled non-live.
- **V2 optimization proposal** (`frontend/PerformanceStage.jsx`): the V2 "Enviar a aprobación" button calls `PerformanceApi.proposal(campaign, { source_revision_id, status: "sent_to_approval", ... })`.

`frontend/lib.jsx` adds `GenerationApi.latestRevision(campaign)` (picks the highest `revision_number`) and the `ReviewApi` thread helpers (`ensureThread`, `approve`, `requestChangesThread`, `addComment`, `resolveCommentSafe`) that all return the `{ ok, fallback, reason, data }` envelope. The frontend smoke script exercises every one of these and asserts either backend success or fail-closed.

## Deferred/non-MVP gaps

- Full Next.js/Tailwind migration remains frontend-owned.
- Static adapters should be replaced during that migration.
- Authenticated reviewer identity, real approval-thread UI creation, generated revision selection, and live schedule/publish polling need future frontend app context.
- PDF/Figma extraction, live Shopify sync, custom persona/model support, live analytics ingestion, full Lighthouse automation, and live model-generated A/B/C exploration are not part of the deterministic smoke path.
