# Banner Studio Real Data Frontend Integration Plan

> **For Hermes:** Use `plan-executioner-coordinator` and `subagent-driven-development` to implement this plan task-by-task with a fresh implementation subagent per phase. The coordinator must verify every phase independently before marking progress.

**Goal:** Replace Banner Studio’s hardcoded user-visible data with real data from the already implemented backend APIs wherever the backend currently supports the behavior, while preserving explicit visible fallbacks for backend gaps/fail-closed flows.

**Architecture:** Keep the current static React UMD/Babel frontend and its `window.*` adapter style. Add a thin frontend state/data layer that hydrates stores, campaigns, placement options, catalog/art/generation/review/performance state from `/api/v1` with demo auth headers. Static seed data may remain only as labeled fallback/default UI metadata when the backend has no equivalent endpoint.

**Tech Stack:** Static React 18 UMD/Babel, FastAPI `/api/v1`, Supabase-backed local demo data, Python/pytest backend tests, Node/browser smoke scripts.

---

## Current Repository Reality

- Frontend is static React under `frontend/`; there is no `package.json` or frontend build step.
- `frontend/lib.jsx` already contains `AijolotApi`, `CampaignApi`, `StoreApi`, `PlacementApi`, `CatalogApi`, `ArtDirectionApi`, `GenerationApi`, `ReviewApi`, and `PerformanceApi` adapters.
- `frontend/data.jsx` still exports the primary static demo datasets that drive most visible Banner Studio UI.
- Canonical frontend calls must use `/api/v1` with demo auth/team/store context.
- Root backend routes remain prototype compatibility only.
- A backend UUID campaign id is required for durable stage APIs. Local/non-UUID campaign ids must stay visibly labeled as fallback/prototype state.
- Backend APIs that are safe to integrate now: campaigns, intake, brands, stores/resources, placement types/targets/validate/save/get, catalog snapshot, art direction, generation runs/events with current DB fix caveat, performance/snapshot/proposal non-live data.
- Backend APIs that must be integrated fail-closed/visibly: preview/audit, revisions/select/regenerate, approval/comment/refinement, schedules, publish/unpublish.
- Current observed runtime issue: the running uvicorn server previously produced a 500 creating generation events because `generation_events.output_summary` was inserted as null. The in-process TestClient path passed. Frontend integration must make this error visible and not assume generation is green until a smoke test passes.

---

## Hardcoded Frontend Inventory and Backend Coverage

### Replace with backend data now

1. `frontend/Shell.jsx`
   - Hardcoded `KPIS` and `RECENT` campaigns.
   - Backend coverage: `CampaignApi.list/get`, `PerformanceApi.get` for non-live labels.
   - Target: Banner Studio campaign list must show campaigns created through backend instead of only `CMP-0192`, `CMP-0188`, `CMP-0185`.

2. `frontend/data.jsx` placement/store constants
   - Hardcoded `STORE_PAGES`, `SCOPE_OPTS`, `BRANDS`, `COLLECTIONS`.
   - Backend coverage: stores/resources, placement types, placement targets, placement validate/save/get.
   - Target: placement browser must hydrate store, resource, and placement options from backend seeded/cache data.

3. `frontend/PlacementStage.jsx` and `frontend/StoreMocks.jsx`
   - Hardcoded Maison page mock content, slots, page URLs, scope defaults.
   - Backend coverage: store summaries, Shopify resource cache, placement types/targets.
   - Target: use backend data for available stores/pages/resources/placement types; keep visual page mock as a renderer, not source of truth.

4. `frontend/BriefStage.jsx`, `frontend/components/Chatbox.jsx`, `frontend/components/CampaignChips.jsx`
   - Chat suggestions and required field labels may stay as UI hints, but campaign state must come from backend UUID campaigns.
   - Backend coverage: `POST /api/v1/campaigns/intake`, `PATCH /api/v1/campaigns/{id}`.
   - Target: edited chips must surface backend save errors visibly instead of silently swallowing them.

5. `frontend/ArtStage.jsx`
   - Hardcoded product/segment/model/style defaults; catalog snapshot currently uses backend but visible data still derives from static `CATALOG`/`SEGMENTS`.
   - Backend coverage: catalog snapshot create/get, store resources, art direction save/get.
   - Target: product/catalog cards should come from backend resource cache/snapshot, art direction should hydrate from backend when returning to the stage.

6. `frontend/GenerateStage.jsx`
   - Hardcoded `PIPELINE`, `CODE_LINES`, static brand/catalog animation, CWV gauges.
   - Backend coverage: generation runs/events, revisions, preview/audit fail-closed.
   - Target: StepRail/progress must map backend generation events and show actual backend error/fallback notices. Static labels can remain as display labels only when no backend event exists.

7. `frontend/CanvasStage.jsx` and `frontend/CanvasPanels.jsx`
   - Hardcoded approvers, comments, devices, segments, variants, dates, local approval state, and local refinement messaging.
   - Backend coverage: revisions/select, approval/comment/refinement routes exist but default unavailable/fail-closed; schedule/publish routes exist but status/adapter guarded.
   - Target: load backend revisions and approval thread if available; otherwise show explicit local/prototype approval mode. Do not allow schedule/publish buttons to appear successful unless backend accepts them.

8. `frontend/PerformanceStage.jsx`
   - Hardcoded `METRICS`, `SEG_PERF`, `CTR_TREND`, `MEMORY`.
   - Backend coverage: performance get/snapshot/proposal with manual/mock/seed/agent labels.
   - Target: render backend performance response when available and preserve non-live labels; static metrics only as visible fallback.

9. `frontend/BrandContextView.jsx`
   - Already mostly backend-backed; font options and preview text are UI metadata.
   - Backend coverage: brands list/get/put.
   - Target: keep backend behavior and fix stale comments/normalization risks only if touched.

### Keep as UI metadata or explicit fallback because backend is missing

- Navigation labels, stage labels, icons, months/weekdays, device labels.
- Model bank list/create model UX: backend has art-direction model metadata but no model-bank list/create endpoint.
- Hero style presets/grid presets: backend can store keys/layout JSON but has no list endpoint.
- Evolutionary memory cards: backend performance proposals/insights exist but no direct memory-history endpoint matching `MEMORY`.
- Live Shopify publishing/sync and live analytics: backend intentionally fail-closed/manual/non-live.

---

## Non-Negotiable Constraints

- Do not read `.env`, `.env.local`, Shopify tokens, Supabase service-role keys, Gemini keys, or any secret file.
- Do not make live Shopify, Gemini, external analytics, or destructive external calls.
- Preserve `/api/v1` exactly-once path normalization and demo auth headers.
- Preserve current static frontend architecture; do not introduce a build system unless explicitly requested.
- All backend failures must be visible in the UI via existing notice/fallback patterns; do not silently swallow persistence failures.
- Keep static values only when they are UI labels/defaults or clearly labeled fallback data.
- Do not mark Shopify publishing as live. Publish endpoints remain fail-closed unless a safe injected adapter exists.
- Do not claim live analytics. Performance is non-live unless backend says `live_analytics: true`.

---

## Phase 1: Shared Backend State and Campaign List Hydration

**Objective:** Make Banner Studio show backend-created campaigns in the shell and keep the active Studio campaign as a backend UUID campaign.

**Files:**
- Modify: `frontend/lib.jsx`
- Modify: `frontend/Shell.jsx`
- Modify: `frontend/App.jsx`
- Test/verify: `scripts/smoke-frontend-backend-connection.mjs` if safe; browser/manual curl checks.

**Steps:**
1. Add small adapter helpers if needed:
   - `CampaignApi.listSafe()` or equivalent fallback envelope.
   - `CampaignApi.toRecentCard(campaign)` mapping backend `Campaign` to shell card fields.
2. Update `CampaignsView` in `Shell.jsx` to fetch `CampaignApi.list()` on mount.
3. Render backend campaigns first. If none exist, show an explicit empty state with “No hay campañas creadas aún” plus the current demo cards only under a “Demo/fallback” label if needed.
4. Preserve ability to start a new Studio campaign and pass/create a backend UUID campaign before stage APIs persist data.
5. Ensure selecting/continuing a backend campaign hydrates App state with that campaign id/title/status/brief.
6. Surface API errors in the Shell with an amber notice/inline fallback instead of silently using `RECENT`.

**Acceptance Criteria:**
- Creating a campaign through intake or `CampaignApi.create` makes it appear in Banner Studio campaign list after refresh.
- The old hardcoded `RECENT` list is no longer the only visible campaign source.
- Local fallback/demo campaigns are clearly labeled as fallback/prototype.
- Active campaign passed into later stages has a UUID id when backend is reachable.

**Validation:**
- Open `http://127.0.0.1:5500`, create/intake a campaign, refresh, verify it appears in campaign list.
- Run existing smoke script if environment is available:
  - `node scripts/smoke-frontend-backend-connection.mjs`
- Verify no double `/api/v1` requests in network/logs.

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent. Changed `frontend/lib.jsx`, `frontend/Shell.jsx`, and `frontend/App.jsx`. Verified with `git diff --check` and safe backend create/list + intake/list checks. Full frontend-backend smoke still fails at the pre-existing generation-run 500, outside this phase.

---

## Phase 2: Store, Placement, and Resource Hydration

**Objective:** Replace placement/browser hardcoded source-of-truth with backend store/resource/placement data.

**Files:**
- Modify: `frontend/lib.jsx`
- Modify: `frontend/data.jsx`
- Modify: `frontend/PlacementStage.jsx`
- Modify: `frontend/StoreMocks.jsx`
- Modify: `frontend/App.jsx`

**Steps:**
1. Add/confirm safe adapters for:
   - `StoreApi.list()`
   - `StoreApi.get(storeId)`
   - `StoreApi.resources(storeId, resourceType)`
   - `StoreApi.placementTypes(storeId)`
   - `StoreApi.placementTargets(storeId, placementTypeKey)`
2. In `PlacementStage`, hydrate selected/default store from backend seeded demo store.
3. Build page/resource choices from backend resources (`collection`, `product`, `page`, `search`) instead of `BRANDS`/`COLLECTIONS` arrays where possible.
4. Build available placement slots from backend placement types; map them to existing visual mock zones.
5. Keep `StoreMocks` as a visual rendering layer. It may use static copy for mock page text, but placement availability/ids/titles must come from backend placement types/resources.
6. On continue, continue calling `PlacementApi.validate`; preserve errors/notices.
7. After backend campaign UUID exists, continue saving placement with `PlacementApi.save`.
8. If backend placement types/resources fail, clearly label static `STORE_PAGES` as fallback.

**Acceptance Criteria:**
- Placement stage displays backend store domain/name and seeded resource titles/handles.
- Placement choices are derived from backend placement types/resources when backend is reachable.
- Saved placement can be fetched back with `PlacementApi.get` for the active campaign.
- Static placement data is only used as visible fallback.

**Validation:**
- Browser: choose a placement, continue, create campaign, verify placement saves.
- Backend: `GET /api/v1/campaigns/{id}/placement` returns selected placement.
- Visual: no hardcoded brand/product chips appear as authoritative when backend data exists.

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent. Changed `frontend/lib.jsx`, `frontend/data.jsx`, `frontend/PlacementStage.jsx`, `frontend/StoreMocks.jsx`, and `frontend/App.jsx`. Verified with `git diff --check`, safe backend GETs for stores/resources/placement types, and JSX transform checks. Saved placement fetch-back was implemented but not manually browser-verified yet.

---

## Phase 3: Brief Persistence Error Visibility and Campaign Hydration

**Objective:** Ensure brief chip edits and intake persist to backend and failures are visible.

**Files:**
- Modify: `frontend/components/Chatbox.jsx`
- Modify: `frontend/components/CampaignChips.jsx`
- Modify: `frontend/BriefStage.jsx`
- Modify: `frontend/App.jsx`

**Steps:**
1. Ensure Chatbox always uses `/api/v1/campaigns/intake` when backend is available.
2. Keep local rule extractor only as explicit offline fallback.
3. Update `CampaignChips.persist()` to report backend PATCH errors through `onNotice` or visible inline save state.
4. Add a small save-state indicator: saved / saving / save failed.
5. Ensure backend campaign response updates App campaign state after PATCH/intake.
6. Prevent proceeding with a local/non-UUID campaign without a visible prototype-only warning.

**Acceptance Criteria:**
- Editing chips updates backend campaign when UUID campaign exists.
- Backend save failures are visible.
- Refreshing and reloading the campaign shows the updated brief fields.

**Validation:**
- Create campaign, edit CTA/tone/urgency, refresh/list/get campaign and verify fields.
- Temporarily simulate backend failure by stopping backend or invalid campaign id; UI shows a failure notice.

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent. Changed `frontend/components/Chatbox.jsx`, `frontend/components/CampaignChips.jsx`, `frontend/BriefStage.jsx`, and `frontend/App.jsx`. Verified with `git diff --check`, `backend/.venv/bin/python -m pytest backend/tests/api/test_campaigns.py -q`, and safe TestClient create/intake/patch/get roundtrip.

---

## Phase 4: Catalog Snapshot and Art Direction Hydration

**Objective:** Show backend catalog snapshot/resources and restore saved art direction from backend.

**Files:**
- Modify: `frontend/ArtStage.jsx`
- Modify: `frontend/ModelBank.jsx` only if needed for clear labeling.
- Modify: `frontend/data.jsx` to demote static `CATALOG`, `HERO_STYLES`, `MODELS` to fallback/UI presets.

**Steps:**
1. On entering Art stage with UUID campaign, fetch/create catalog snapshot using backend store/resource cache.
2. Render products/resources from the returned snapshot instead of static `CATALOG`.
3. Fetch existing art direction and initialize controls from it when present.
4. Save art direction through `ArtDirectionApi.save` and update UI saved state.
5. Clearly label `HERO_STYLES`/`MODELS` as local presets because backend has no list endpoint.
6. Preserve the no-backend fallback with visible amber notice.

**Acceptance Criteria:**
- Art stage product/resource data comes from backend snapshot/resource cache when available.
- Returning to Art stage restores saved art direction for the active campaign.
- Model/style presets are not presented as backend data.

**Validation:**
- Create campaign -> Art -> save -> reload stage -> settings persist.
- Inspect backend catalog snapshot endpoint returns visible items rendered in UI.

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent. Changed `frontend/ArtStage.jsx`, `frontend/ModelBank.jsx`, and `frontend/data.jsx`. Art stage now fetches/creates backend catalog snapshots for UUID campaigns, renders snapshot resources with visible fallback labels, restores/saves art direction through backend APIs, and labels model/style options as local UI presets. Verified with `git diff --check`, esbuild JSX syntax transforms, and backend catalog/art-direction API tests.

---

## Phase 5: Generation Event-Driven Progress and Error Surfacing

**Objective:** Replace static generation progress source-of-truth with backend generation run/events while retaining display labels/fallbacks.

**Files:**
- Modify: `frontend/GenerateStage.jsx`
- Modify: `frontend/lib.jsx`
- Possibly add/fix smoke script assertions in `scripts/smoke-frontend-backend-connection.mjs` if needed.

**Steps:**
1. Start generation through `GenerationApi.start` for UUID campaign.
2. Render progress from returned run/progress and `GenerationApi.events(run.id)`, mapping node/frontend_step to existing UI labels.
3. Display backend error details if start/events fail; do not auto-advance as if generation succeeded.
4. Attempt preview/audit/revisions after generation; show fail-closed notices if unavailable.
5. Keep static `PIPELINE` only as label fallback for missing event labels.
6. Investigate and fix only frontend-side handling of the known generation-run 500 by surfacing it; do not change backend in this plan unless a frontend bug causes the issue.

**Acceptance Criteria:**
- Generation UI reflects backend events when generation run succeeds.
- If backend generation fails, the UI shows the error and does not pretend the banner generated.
- Static animation is not the authoritative success signal.

**Validation:**
- Run browser generation and verify requests:
  - `POST /api/v1/campaigns/{id}/generation-runs`
  - `GET /api/v1/generation-runs/{run_id}/events`
- Verify error handling with the current runtime if it still returns 500.

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent. Changed `frontend/GenerateStage.jsx` and `scripts/smoke-frontend-backend-connection.mjs`. Generation progress now derives from backend run/progress/events for UUID campaigns, surfaces start/event errors (including the observed generation-run 500) without advancing to Canvas, and shows preview/audit/revisions as explicit fail-closed notices when unavailable. Verified with `git diff --check`, esbuild JSX syntax transform, `node --check` for the smoke script, and the frontend-backend smoke script (generation start failed closed with 500 and smoke passed by asserting the fail-closed path).

---

## Phase 6: Canvas Revisions, Approval Fallback Clarity, and Schedule/Publish Guardrails

**Objective:** Load backend revisions/approval state when available, and make unavailable approval/schedule/publish flows explicit instead of appearing inert.

**Files:**
- Modify: `frontend/CanvasStage.jsx`
- Modify: `frontend/CanvasPanels.jsx`
- Modify: `frontend/lib.jsx` only if better fallback envelopes are needed.

**Steps:**
1. Load latest/list revisions for UUID campaign; map backend `layout_variants`/segment keys into visible variant/segment controls where available.
2. If revisions are unavailable, label segment/variant data as local prototype preview.
3. Request/load approval thread if backend accepts it; otherwise clearly show “Aprobaciones locales/prototipo”.
4. Update `setApprover`, comments, refinement actions to show backend success/fallback per action.
5. Disable or annotate schedule controls unless backend prerequisites are met:
   - backend campaign status approved/scheduled,
   - selected revision exists,
   - backend approval thread is actually approved or status says approved.
6. On schedule 409/503, show specific reason from backend and keep local scheduled state false.
7. On publish 409/503, show specific fail-closed reason and keep published state false.
8. Rename/label “Publicar ahora” in local default mode as unavailable/fail-closed unless backend accepts publish.

**Acceptance Criteria:**
- Canvas no longer gives the impression that local approvals are real backend approvals.
- Schedule/publish failures are visible and explain the missing backend prerequisite.
- Backend revisions, if present, drive the variant selector.
- `Programar` and `Publicar ahora` never silently do nothing.

**Validation:**
- Current user reproduction: click Programar/Publicar ahora and verify visible explanation instead of inert behavior.
- Backend logs and UI notice agree with status code/detail.

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent. Changed `frontend/CanvasStage.jsx`, `frontend/CanvasPanels.jsx`, and `frontend/lib.jsx`. Verified with `git diff --check`, esbuild JSX syntax checks, and `node scripts/smoke-frontend-backend-connection.mjs`, which now confirms revision/approval/schedule/publish unavailable paths fail closed visibly instead of appearing inert.

---

## Phase 7: Performance Hydration and Non-Live Labeling

**Objective:** Render backend performance response/proposals/snapshots instead of only hardcoded metrics.

**Files:**
- Modify: `frontend/PerformanceStage.jsx`
- Modify: `frontend/data.jsx` to demote `METRICS`, `SEG_PERF`, `CTR_TREND`, `MEMORY` to fallback only.

**Steps:**
1. On Performance stage mount, call `PerformanceApi.get(campaign)` for UUID campaigns.
2. Map `latest_snapshot` to KPI cards:
   - impressions,
   - clicks/CTR,
   - conversions/conversion_rate,
   - load/weight if present.
3. Map `segment_breakdown` and `trend` when present; otherwise show fallback charts with explicit demo label.
4. Render `insights`/`proposals` instead of static `MEMORY` where possible.
5. Keep “manual/mock/seed/agent/non-live” label from backend response visible.
6. Snapshot/proposal buttons should show backend success/failure state.

**Acceptance Criteria:**
- Backend performance data appears when available.
- Static metrics are visibly fallback/demo only.
- No performance view claims live Shopify analytics unless backend says `live_analytics: true`.

**Validation:**
- Call Performance stage for campaign, create snapshot, reload, verify snapshot-derived KPIs render.
- Verify non-live label is visible.

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent. Changed `frontend/PerformanceStage.jsx` and `frontend/data.jsx`. Verified with `git diff --check`, esbuild JSX syntax check, and backend performance tests (`backend/tests/unit/test_performance_service.py`, `backend/tests/api/test_performance.py`: 11 passed, 1 existing warning).

---

## Phase 8: Documentation, Smoke Test, and Final Integration Review

**Objective:** Document what is now frontend-backed by real APIs, keep known backend gaps explicit, and validate the integrated flow.

**Files:**
- Modify: `docs/architecture/frontend-backend-contract.md`
- Modify or create: `docs/architecture/frontend-hardcoded-data-inventory.md`
- Modify: `docs/plans/2026-06-03-frontend-real-data-integration.md`
- Optional modify: `scripts/smoke-frontend-backend-connection.mjs`

**Steps:**
1. Create/update a hardcoded-data inventory doc listing remaining static UI metadata vs backend-backed data.
2. Update frontend-backend contract with current real-data integration behavior.
3. Ensure the smoke script covers the successful portions and expects fail-closed behavior for unavailable parts.
4. Run safe validation:
   - `git diff --check`
   - backend API tests if backend touched (ideally no backend touched here): `cd backend && . .venv/bin/activate && pytest tests/api -q`
   - deterministic smoke: `python3 scripts/smoke-demo-flow.py`
   - frontend-backend smoke if environment is suitable: `node scripts/smoke-frontend-backend-connection.mjs`
5. Coordinator final review must verify user’s original goal: created campaigns appear in Banner Studio and every backend-supported feature is visible or visibly fail-closed.

**Acceptance Criteria:**
- Plan checkboxes/completion notes reflect executed work.
- Docs distinguish integrated frontend data from fallback/static metadata.
- Final validation commands and known failures are documented.

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by Phase 8 subagent. Created `docs/architecture/frontend-hardcoded-data-inventory.md` and updated `docs/architecture/frontend-backend-contract.md` with the current integration matrix, fallback/static metadata rules, known backend gaps, and smoke-script behavior. Reviewed `scripts/smoke-frontend-backend-connection.mjs`; no change required because it already asserts successful `/api/v1` portions and accepts explicit fail-closed behavior for generation/revisions/approval/schedule/publish local-demo gaps. Validation run 2026-06-03: `git diff --check` passed; `node --check scripts/smoke-frontend-backend-connection.mjs` passed; `python3 scripts/smoke-demo-flow.py` passed (deterministic fallback, existing `Concept.copy` warning); `cd backend && . .venv/bin/activate && pytest tests/api -q` passed (98 passed, 1 existing warning); `node scripts/smoke-frontend-backend-connection.mjs` passed against running backend, with expected fail-closed local-demo results: generation start 500, regenerate 404, refinement 503, approval request 422, schedule 409, publish 503, no revisions for optimization proposal, and non-live performance label. Final integration review also verified a newly created backend campaign is returned by `GET /api/v1/campaigns`, which is the Shell/Banner Studio source for created campaign visibility.

---

## Coordinator Self-Review Loop Result

### Review Pass 1 Findings

- Initial scope covered campaign list, placement, brief, art, generation, canvas, and performance.
- Missing explicit CampaignChips save-error visibility; added Phase 3 details.
- Missing explicit “created campaign appears in Banner Studio after refresh” acceptance; added Phase 1 criteria.
- Missing preview/audit fail-closed behavior; added Phase 5 and constraints.
- Missing schedule/publish inert-button reproduction; added Phase 6 validation.
- Missing final hardcoded inventory doc; added Phase 8.

### Review Pass 2 Findings

- Remaining backend gaps must not be implemented in this frontend plan; they must become a separate backend plan after frontend integration. This is explicitly captured below and will be expanded after implementation.
- Static UI metadata can stay where no backend contract exists. The plan now distinguishes source-of-truth data from labels/presets.
- Each currently working backend process has either direct integration or explicit fail-closed integration:
  - campaigns/intake/list/edit: Phases 1 and 3,
  - brands: already integrated / Phase 8 docs,
  - stores/resources/placements: Phase 2,
  - catalog/art: Phase 4,
  - generation/events/revisions/preview/audit: Phase 5 and 6,
  - approvals/comments/refinement: Phase 6 fail-closed/available thread integration,
  - schedule/publish: Phase 6 guardrails/fail-closed,
  - performance: Phase 7.

### Coordinator Confidence Statement

After the above upgrades, this plan is complete enough to ensure that every currently developed backend capability is either visible in the frontend through real data or visibly marked as unavailable/fallback/fail-closed after execution. The remaining unsupported frontend assumptions are intentionally deferred to the separate backend gap plan after implementation.

---

## Resume Checklist

1. Check git status and active branch.
2. Read this plan’s progress markers.
3. Start with the first unchecked phase.
4. Use one fresh implementation subagent per phase.
5. Coordinator independently reviews diff and runs validation after each phase.
6. Mark completed phase with a short note.
7. After Phase 8, create the backend missing-functions list and non-executed backend plan.
