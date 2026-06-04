# Aijolot Banner Agent MVP Gap Closure Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task. Do not execute this plan until Pk approves. Keep demo reliability first, use focused branches from `main`, and verify after every phase.

**Goal:** Close the remaining gaps between the current `main` codebase and a showcase-ready Aijolot Banner Agent MVP, with special priority on the agentic generation path, backend-selected revisions, approval/schedule/publish demo flow, and visible frontend UX guardrails.

**Architecture:** Keep `/api/v1` as the canonical contract and preserve the current static React frontend. For the hackathon demo, implement a deterministic, fully persisted local/Supabase happy path that is honest about provider fallbacks, while wiring the real agent pipeline behind an opt-in/feature flag where it is safe. Keep real Shopify/Gemini/live analytics fail-closed unless explicitly configured for a safe test store/provider.

**Tech Stack:** FastAPI, Pydantic v2, Supabase/Postgres, Google ADK Workflow, deterministic local agent skills, optional Gemini/Gemini Image, static React 18 UMD/Babel, pytest/httpx, Node smoke scripts.

---

## Current Repository Reality Verified 2026-06-03 18:53 CST

- Repo: `/Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent`
- Branch: `main`, tracking `origin/main`
- Worktree: clean before writing this plan.
- Recent merges on `main` include:
  - `4fa1a38` Merge PR #16 `feature/frontend-real-data-integration`
  - `5541fbf` Merge PR #17 `backend/adk-skills-contracts`
  - `9299b9f` Merge PR #15 `feat/gh-7-4-pg-cron-scheduler`
- Existing docs reviewed:
  - `docs/architecture/frontend-assumed-backend-gaps.md`
  - `docs/plans/2026-06-03-frontend-real-data-integration.md`
  - `docs/plans/2026-06-03-backend-gap-closure-plan.md`
  - `docs/architecture/frontend-hardcoded-data-inventory.md`
  - `docs/architecture/frontend-backend-contract.md`
- Current frontend/backend smoke state reported by inspection/smoke:
  - `node scripts/smoke-frontend-backend-connection.mjs` passes by accepting explicit fail-closed gaps.
  - Current fail-closed/local-demo states still include generation `500`, no revisions, regenerate `404`, refinement `503`, approval `422`, schedule `409`, publish `503`, and non-live performance label.

---

## Gap Status Matrix From `frontend-assumed-backend-gaps.md`

| # | Gap | Current state on `main` | MVP action |
|---|-----|-------------------------|------------|
| 1 | Generation run runtime DB failure | Partially done. Event repository now omits `None` values and DB has non-null default, but real Supabase/migration-shaped regression coverage is missing and smoke still observes generation `500`. | Must fix first. |
| 2 | Real revision creation and selected revision availability | Partially done. Revision/select/regenerate services exist, but initial generation does not create selected revision, variants, preview, or audit artifacts. | Must fix first. |
| 3 | Preview and audit availability | Partially done. Routes exist but depend on revision/artifact/RLS state and are not created by generation. | Must fix for demo. |
| 4 | Approval service default unavailable | Partially done. Approval service/tests exist, but `configured_service_for_team(...)` still raises unavailable in default runtime. | Must fix for demo approval. |
| 5 | Refinement/regeneration full path | Partially done. Regeneration mechanics exist, but blocked by missing initial revision and unavailable approval/refinement default service. | Include after base happy path. |
| 6 | Scheduling happy path | Partially done. Service works when campaign is approved and has selected revision; demo path cannot reach those prerequisites yet. | Fix after approval/revision. |
| 7 | Shopify publish adapter | Partially done. Publisher logic and fake tests exist; default real publisher intentionally returns 503. | For MVP, either safe fake publish success with clear demo label or real safe test-store adapter only with explicit approval. |
| 8 | Live Shopify resource sync | Missing. Read endpoints use Supabase cache or deterministic seed data; no live sync/import endpoint. | Defer unless demo requires live sync; keep seeded/cache label. |
| 9 | Model bank list/create endpoint | Missing. Art direction stores `model_key`/`custom_model`, but no model-bank API. | Defer or add simple read-only registry if visible demo needs it. |
| 10 | Hero style/grid registries | Missing. Stored as art direction/layout JSON only; no registry endpoints. | Defer or add simple read-only registry if visible demo needs it. |
| 11 | Evolutionary memory history endpoint | Missing. Performance insights/proposals exist, but no team/campaign learning-memory endpoint matching frontend cards. | Nice-to-have after happy path. |
| 12 | Live analytics ingestion | Missing. Manual/mock/seed/agent performance exists; no live ingestion job. | Defer; preserve non-live labels. |
| 13 | Brand import UI helper parity | Backend done. `POST /api/v1/brands/import` exists. Remaining parity is frontend copy/UI if desired. | Minor frontend cleanup only. |

MVP critical path: 1 -> 2 -> 3 -> agentic integration -> 4 -> 6 -> 7 demo-safe publish -> frontend UX fixes.

---

## Agentic Functions Current State and Risk

### What is already done

- Declarative 12-node graph exists in `backend/app/agents/graph.py`:
  1. `load_brand_context`
  2. `intake_campaign_idea`
  3. `capture_user_personalization`
  4. `research_best_practices`
  5. `draft_banner_concept`
  6. `generate_image`
  7. `optimize_assets`
  8. `render_html`
  9. `audit`
  10. `human_review`
  11. `schedule_or_publish`
  12. `publish_to_shopify`
- Actual ADK Workflow builder exists in `backend/app/agents/pipeline.py` with pre-review and post-review pipelines.
- Internal runtime skills under `backend/app/agents/skills/*/impl.py` are mostly real deterministic/local implementations:
  - brand loading, personalization, static KG retrieval, concept drafting, prompt refinement, image fake/provider boundary, optimization, HTML render, Liquid build, performance audit, schedule route.
- Provider boundaries exist:
  - `backend/app/agents/tools/nano_banana_image.py`
  - `backend/app/services/gemini/fake_image_provider.py`
- Topology/skill unit tests exist under `backend/tests/unit/agents/`.

### What is not showcase-safe yet

- `POST /api/v1/campaigns/{campaign_id}/generation-runs` does not execute the ADK pipeline. It uses `GenerationRunService.start_generation_run()` to emit a deterministic progress facade and immediately-succeeded run.
- The generation facade does not create the artifacts the frontend needs: selected revision, variants, preview HTML, audit report, or durable optimized assets.
- The actual ADK pipeline has internal nodes not represented in the 12-node facade (`image-prompt-refine`, `liquid-section-build`, `render_join`), so progress/event mapping can be misleading.
- `hitl-review-handoff` and `resume_after_hitl` remain `NotImplementedError` seams.
- Post-review pipeline is not wired into API state and probably lacks enough state for `shopify-theme-publish`.
- Static KG is lexical/in-code; vector seed/upsert is `NotImplementedError` in `scripts/kg_seed.py`.
- Real Gemini/Gemini Image should remain opt-in. The demo can honestly say deterministic/local provider unless keys are configured.

### MVP stance

For the hackathon showcase, do not try to fully solve asynchronous ADK/HITL/resume/live providers if time is short. Instead:

1. Make the main generation endpoint produce real persisted MVP artifacts using the existing deterministic skills or an adapter around them.
2. Expose truthful generation events from the skill chain, not just synthetic facade-only events.
3. Keep a feature flag for future full ADK execution, but make the default demo deterministic, fast, persisted, and testable.
4. Label provider mode in frontend/backend responses: `deterministic_demo`, `gemini`, `fake_image_provider`, `static_kg`, etc.

---

## Undocumented Visible Gaps Added by This Review

These are not fully captured in `frontend-assumed-backend-gaps.md`, but they affect the MVP demo:

1. `frontend/App.jsx`: Campaign list “Continuar” resumes every campaign into `canvas`, even draft/no-revision campaigns. It should route by status/artifacts to placement/brief/art/generate/canvas.
2. `frontend/App.jsx`: “Nueva campaña” creates a backend draft immediately before brief input, producing orphan “Nueva campaña” rows if abandoned.
3. `frontend/Shell.jsx`: KPI cards are still hardcoded and look authoritative: active campaigns, published banners, average CTR, saved weight.
4. `frontend/GenerateStage.jsx` and `frontend/CanvasStage.jsx`: Rendered creative preview still uses static `Banner`/`SEGMENTS`/`CATALOG` content even if backend preview/revision exists.
5. `frontend/ArtStage.jsx`: Art stage calls `onAssemble(art)` even when backend catalog/art-direction persistence fails.
6. `frontend/CanvasPanels.jsx`: Schedule defaults are stale/past-dated (`2026-06-02T09:00`) relative to current demo date.
7. `frontend/BrandContextView.jsx`: Copy says brand edits persist to `brands/{id}.md`, which is misleading now that frontend uses `/api/v1/brands`.
8. `scripts/smoke-frontend-backend-connection.mjs`: It checks endpoints, not visible browser/UI labels or resume-stage routing.

These are included in Phase 7 and Phase 8 below.

---

## Implementation Strategy for a Showcase in a Few Hours

Prioritize vertical demo continuity over post-MVP completeness.

### Must-have before showcase

- Backend generation endpoint succeeds in local/Supabase runtime.
- Generation creates selected revision, layout/banner variants, preview HTML, and audit report.
- Canvas can show backend-backed revision/preview, not only local prototype data.
- Approval can be completed in local demo and transitions status to `approved`.
- Schedule can be created after approval.
- Publish can show a credible, safe result:
  - either real Shopify test-store publish if credentials/test theme are explicitly approved, or
  - deterministic demo publisher that writes publish job + payload and clearly labels it as simulated/dry-run.
- Agentic functions are honestly represented: deterministic skill chain produces copy/prompt/image/HTML/audit artifacts, with provider mode surfaced.
- Visible frontend gaps above do not confuse the demo.

### Should defer unless must-have is complete

- Live Shopify resource sync.
- Model-bank create/upload backend.
- Style/grid registry endpoints.
- Learning-memory endpoint.
- Live analytics ingestion.
- Full ADK asynchronous HITL/resume semantics.
- Vector KG ingestion.

---

## Phase 0: Baseline Reproduction and Safety Branch

**Objective:** Establish the current failing baseline and isolate implementation work.

**Files:**
- No production code changes in this phase.
- Create implementation branch from `main`.

**Steps:**
1. Run:
   - `git status --short --branch`
   - `git checkout main`
   - `git pull --ff-only`
   - `git checkout -b feature/mvp-gap-closure-demo-flow`
2. Run backend smoke/tests:
   - `cd backend && . .venv/bin/activate && pytest tests/api/test_generation_runs.py tests/unit/test_generation_run_service.py -q`
   - `python3 scripts/smoke-demo-flow.py`
   - `node scripts/smoke-frontend-backend-connection.mjs`
3. Save baseline output in the task notes, not in committed docs unless useful.
4. Confirm no secrets are read and no live Shopify/Gemini calls occur.

**Expected result:** Baseline confirms the same fail-closed generation/revision/approval/schedule/publish states listed above.

**Commit:** No commit unless docs/baseline notes are intentionally updated.

**Progress:** [x] Completed 2026-06-03

Coordinator note: Created branch `feature/mvp-gap-closure-demo-flow` from updated `main`. Baseline validation passed for existing tests and documented current fail-closed behavior: `cd backend && . .venv/bin/activate && pytest tests/api/test_generation_runs.py tests/unit/test_generation_run_service.py -q` passed (16 passed, 1 existing `Concept.copy` warning); `python3 scripts/smoke-demo-flow.py` passed; `node scripts/smoke-frontend-backend-connection.mjs` passed while confirming generation 500, no revisions, regenerate 404, refinement 503, approval 422, schedule 409, publish 503, and non-live performance label.

---

## Phase 1: Fix Generation Runtime and Persist MVP Artifacts

**Objective:** `POST /api/v1/campaigns/{campaign_id}/generation-runs` must succeed in local Supabase and create the backend artifacts required by the frontend.

**Files:**
- Modify: `backend/app/services/banners/generation_run_service.py`
- Modify: `backend/app/db/repositories/generation_events.py` only if needed
- Modify/Create: `backend/app/services/banners/revision_service.py`
- Modify/Create: `backend/app/services/banners/html_renderer.py`
- Modify/Create: `backend/app/services/banners/audit_report_service.py` or existing equivalent
- Modify/Create tests:
  - `backend/tests/unit/test_generation_run_service.py`
  - `backend/tests/api/test_generation_runs.py`
  - `backend/tests/integration/test_generation_supabase_schema.py` if local Supabase integration fixture exists or can be safely added

**Steps:**
1. Add/confirm a regression test that inserted generation events never send `output_summary = null`.
2. Add a service-level test for generation success creating:
   - generation run,
   - ordered events,
   - campaign revision,
   - selected revision pointer,
   - layout variants A/B/C or current frontend-compatible variant set,
   - segment variants if schema supports them,
   - preview HTML,
   - audit report,
   - campaign status transition to `needs_review` or current review-ready status.
3. Implement minimal deterministic artifact creation after the generation event chain succeeds.
4. Make generation idempotent enough for repeated demo clicks:
   - create a new generation run/revision per click,
   - do not mutate previous final assets incorrectly,
   - mark previous selected revision superseded only when new revision succeeds.
5. Ensure errors remain visible and do not create half-selected revisions.
6. Run focused tests and smoke.

**Validation:**
- `cd backend && . .venv/bin/activate && pytest tests/unit/test_generation_run_service.py tests/api/test_generation_runs.py -q`
- `python3 scripts/smoke-demo-flow.py`
- `node scripts/smoke-frontend-backend-connection.mjs`
- Manual API check:
  - create campaign,
  - start generation,
  - get latest run/events,
  - get revisions,
  - get preview,
  - get audit report.

**Acceptance Criteria:**
- No generation `500` in local demo runtime.
- Latest generated campaign has selected revision and preview/audit artifacts.
- Frontend can advance to Canvas only after backend generation success.

**Commit:** `feat: persist demo generation revisions and artifacts`

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented and reviewed through fresh subagents plus coordinator fixes. Changed `backend/app/services/banners/generation_run_service.py`, `backend/app/db/repositories/generation_runs.py`, `backend/app/services/banners/html_renderer.py`, new `backend/app/services/banners/audit_report_service.py`, `backend/app/api/v1/generation.py`, and `backend/tests/unit/test_generation_run_service.py`. Generation now creates runs as `running`, inserts non-null-summary events before artifacts, persists deterministic MVP revision/layout variants/segment variant/preview/audit artifacts in configured repository mode, marks the run `succeeded` only after artifacts, marks failed on persistence errors, and API converts persistence failures to 503. Review loops fixed partial-write risks around campaign update rollback, event-insert ordering, audit normalization, and ignored campaign update results. Validation: focused generation tests passed (24 passed, 1 existing warning); final reviewer ran full backend suite (296 passed, 3 skipped, 1 warning), `python3 scripts/smoke-demo-flow.py`, `node scripts/smoke-frontend-backend-connection.mjs`, and `git diff --check` successfully.

---

## Phase 2: Wire Deterministic Agentic Skill Chain Into Generation

**Objective:** Make generation artifacts come from the project’s agentic functions, not only a synthetic facade, while preserving a deterministic demo mode.

**Files:**
- Modify: `backend/app/services/banners/generation_run_service.py`
- Modify/Create: `backend/app/agents/pipeline_runner.py`
- Modify/Create: `backend/app/agents/workflows/banner_creation.py` or service adapter
- Modify: `backend/app/agents/state_bridge.py`
- Modify tests:
  - `backend/tests/unit/agents/test_pipeline.py`
  - `backend/tests/unit/agents/test_context_and_concept_skills.py`
  - `backend/tests/unit/agents/test_audit_skill.py`
  - `backend/tests/unit/test_generation_run_service.py`

**Steps:**
1. Add a small `AgenticGenerationAdapter` or equivalent service boundary with two modes:
   - `deterministic_demo`: directly run existing deterministic skill functions in sequence and return a normalized artifact bundle.
   - `adk_pipeline`: optional, feature-flagged, runs `build_pre_review_pipeline()` only when safe and testable.
2. Normalize output into a single artifact bundle:
   - concept/copy,
   - refined image prompt,
   - image asset/provider metadata,
   - optimized asset metadata,
   - rendered HTML preview,
   - Liquid payload/config,
   - audit result,
   - event list with node keys and frontend steps,
   - provider/fallback provenance.
3. Align event names with actual nodes:
   - include high-level 12-node labels for frontend clarity,
   - optionally include internal substeps (`image-prompt-refine`, `liquid-section-build`, `render_join`) as child/substep metadata.
4. Surface `agent_mode`, `image_provider`, `kg_provider`, and `audit_provider` in run metadata.
5. Keep fake image/static KG explicit and honest.
6. Add tests that generation uses the adapter and persists artifact contents into the revision/preview/audit created in Phase 1.

**Validation:**
- `cd backend && . .venv/bin/activate && pytest tests/unit/agents tests/unit/test_generation_run_service.py -q`
- Confirm no external provider calls occur without explicit env opt-in.
- Confirm generation response/run metadata includes provenance labels.

**Acceptance Criteria:**
- Agentic functions are core to the generation output for demo mode.
- No claim of live Gemini/vector KG/Shopify if deterministic providers are used.
- Existing ADK graph is preserved; no duplicate topology is created.

**Commit:** `feat: run deterministic agentic generation adapter`

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent and independently reviewed. Changed `backend/app/agents/pipeline_runner.py`, `backend/app/services/banners/generation_run_service.py`, `backend/tests/unit/agents/test_pipeline.py`, and `backend/tests/unit/test_generation_run_service.py`. Added `AgenticGenerationAdapter` with deterministic-demo mode that runs existing runtime skills directly (brand context, personalization, static KG, concept draft, prompt refine, fake image generation, image optimization, HTML render, Liquid build, deterministic audit) and preserves `adk_pipeline` as explicit future/feature-gated mode. Generation now persists adapter bundle concept/copy, refined prompt, fake image/optimized asset metadata, HTML preview, Liquid payload, audit output, skill-chain events, and provenance labels (`agent_mode`, `image_provider`, `kg_provider`, `audit_provider`, `shopify_provider`). Review confirmed no live Gemini/Shopify/vector KG/external calls, no duplicate topology, and existing ADK graph preserved. Coordinator fixed minor robustness findings around runtime skill caching/validation and malformed `structured_brief`. Validation: `cd backend && . .venv/bin/activate && pytest tests/unit/agents tests/unit/test_generation_run_service.py -q` passed (67 passed, 1 existing warning); additional phase review ran full backend suite (298 passed, 3 skipped, 1 warning), smoke scripts, and `git diff --check` successfully.

---

## Phase 3: Make Preview, Audit, and Canvas Backend-Backed

**Objective:** Canvas/Generate display real backend artifacts when available.

**Files:**
- Backend verify/fix:
  - `backend/app/api/v1/previews.py`
  - `backend/app/api/v1/generation.py`
  - `backend/app/schemas/*revision*`
- Frontend modify:
  - `frontend/GenerateStage.jsx`
  - `frontend/CanvasStage.jsx`
  - `frontend/CanvasPanels.jsx`
  - `frontend/lib.jsx` if response mapping is missing
- Tests/smoke:
  - `scripts/smoke-frontend-backend-connection.mjs`
  - optional browser smoke script if added in Phase 8

**Steps:**
1. Ensure preview/audit routes work with demo bearer/team context after Phase 1 artifacts exist.
2. In `GenerateStage`, load preview/audit/revisions after generation success and store them in app state.
3. In `CanvasStage`, render backend preview HTML or revision artifact as primary creative when present.
4. Label static `Banner` renderer as local/prototype fallback only.
5. Ensure selected variant/revision controls use backend ids and backend select route.
6. Add smoke assertions that after generation success:
   - revisions list is non-empty,
   - preview returns HTML,
   - audit returns report,
   - Canvas is not only local fallback.

**Validation:**
- `node scripts/smoke-frontend-backend-connection.mjs`
- Browser manual: create -> placement -> brief -> art -> generate -> Canvas shows backend preview/revision label.

**Acceptance Criteria:**
- Generated creative shown in Canvas is backend-backed when generation succeeds.
- Static prototype creative remains only as a visible fallback.

**Commit:** `feat: render generated backend preview in studio`

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent and reviewed/fixed by coordinator. Changed `backend/app/api/v1/previews.py`, new `backend/tests/api/test_previews.py`, `frontend/App.jsx`, `frontend/GenerateStage.jsx`, `frontend/CanvasStage.jsx`, and `scripts/smoke-frontend-backend-connection.mjs`. Preview/audit routes now use request-scoped demo context with team ownership checks and service-role repositories only in local/dev/demo/test environments, fail closed on missing config/auth, and return preview/audit artifacts when configured. GenerateStage now carries preview/audit/revision artifacts to Canvas. Canvas now prioritizes backend preview HTML/revision `html_preview` in a sandboxed iframe with injected CSP meta and visibly labels backend creative vs local/prototype fallback. Smoke script asserts backend creative source wiring and fallback labels. Review fixed service-role demo gating and iframe CSP concerns. Validation: focused preview/generation/revision tests passed (36 passed, 1 existing warning); backend API tests passed (102 passed, 1 warning); final reviewer ran broader backend tests (303 passed, 3 skipped); `node --check`, JSX esbuild checks, `node scripts/smoke-frontend-backend-connection.mjs`, and `git diff --check` passed.

---

## Phase 4: Wire Local Approval, Comments, and Refinement Services

**Objective:** Canvas approval should be real backend state in local demo and unlock scheduling after all reviewers approve.

**Files:**
- Modify: `backend/app/services/approvals/approval_service.py`
- Modify: `backend/app/services/approvals/comment_service.py` if present
- Modify: `backend/app/api/v1/approvals.py`
- Modify/Create repositories under `backend/app/db/repositories/*approval*`, `*comment*`, `*refinement*`
- Modify seed only if necessary: `supabase/seed.sql`
- Tests:
  - `backend/tests/api/test_approvals.py`
  - `backend/tests/unit/test_approval_service.py` if present/create

**Steps:**
1. Replace default `configured_service_for_team(...)` unavailable seam with a Supabase-backed local demo service when request context is valid.
2. Seed or derive deterministic demo reviewers for the demo team.
3. Allow approval request only when a selected revision exists.
4. Persist approval thread, reviewers, comments, and decisions scoped by team/campaign/revision.
5. Transition campaign to `approved` only when all required reviewers approve.
6. Implement request-changes/refinement request persistence and transition to `changes_requested`.
7. Keep no-Supabase/no-auth fallback fail-closed, not silently local shared global state.
8. Update frontend notices if response shape changes.

**Validation:**
- `cd backend && . .venv/bin/activate && pytest tests/api/test_approvals.py -q`
- API flow:
  - generate campaign,
  - request approval,
  - approve all demo reviewers,
  - get campaign status `approved`.
- Browser: Canvas approval panel shows backend mode, not prototype mode.

**Acceptance Criteria:**
- Backend approval works in local demo runtime.
- Campaign status becomes `approved` and schedule prerequisites are reachable.

**Commit:** `feat: enable supabase-backed demo approvals`

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent with multiple security/spec review loops. Changed `backend/app/api/v1/approvals.py`, `backend/app/schemas/approvals.py`, `backend/app/services/approvals/approval_service.py`, `backend/app/services/approvals/comment_service.py`, `backend/tests/api/test_approvals.py`, `backend/tests/unit/test_approval_service.py`, and `supabase/seed.sql`. Default approval/comment endpoints now require request context, are gated to local/test APP_ENV for service-role demo use, bind actor fields (`requested_by`, `author_id`, `resolved_by`, `user_id`) to request context, use team-scoped Supabase-backed repositories when configured, derive deterministic demo reviewers for the seeded demo team, require selected/explicit revisions for approval/refinement, persist threads/reviewers/comments/refinement requests, transition all-reviewer approval to `approved`, and keep no-auth/no-Supabase paths fail-closed. Review fixes addressed spoofable service-role concerns, body actor impersonation, refinement latest-revision fallback, empty thread-create 500s, and wrong-team comment resolve 500s. Validation: approval API/unit tests passed (25 passed, 1 existing warning); backend API tests passed (107 passed, 1 warning); final reviewer ran full backend suite (312 passed, 3 skipped, 1 warning); `python3 scripts/smoke-demo-flow.py`, `node scripts/smoke-frontend-backend-connection.mjs`, and `git diff --check` passed. Note: no-Supabase smoke still shows approval/refinement fail-closed, which is expected without configured Supabase artifact/repository access.

---

## Phase 5: Complete Schedule Happy Path

**Objective:** `Programar` should create a backend schedule after approval and selected revision.

**Files:**
- Verify/modify: `backend/app/services/banners/schedule_service.py`
- Verify/modify: `backend/app/api/v1/schedules.py`
- Verify/modify: `backend/app/db/repositories/schedules.py`
- Frontend modify: `frontend/CanvasPanels.jsx`
- Tests:
  - `backend/tests/unit/test_schedule_service.py`
  - `backend/tests/api/test_schedules.py`

**Steps:**
1. Add an end-to-end backend test: create/intake -> generation -> approval -> schedule.
2. Ensure schedule uses selected revision and approved status.
3. Ensure schedule writes row and transitions campaign to `scheduled`.
4. Fix frontend schedule default dates to be relative to current time:
   - start: now + 1 hour,
   - end: now + 7 days.
5. Validate frontend prevents past/invalid schedule before calling API.
6. Ensure schedule update/cancel remain team-scoped.

**Validation:**
- `cd backend && . .venv/bin/activate && pytest tests/api/test_schedules.py tests/unit/test_schedule_service.py -q`
- Browser: approve campaign -> schedule -> status updates to scheduled.

**Acceptance Criteria:**
- Schedule succeeds in normal demo flow.
- Schedule no longer defaults to a stale/past timestamp.

**Commit:** `feat: complete approved campaign scheduling flow`

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent and independently reviewed. Changed `backend/app/services/banners/schedule_service.py`, `backend/tests/unit/test_schedule_service.py`, `backend/tests/api/test_schedules.py`, and `frontend/CanvasPanels.jsx`. Schedule creation now requires an approved/scheduled campaign with `selected_revision_id`, defaults to the selected revision, rejects explicit non-selected revisions, verifies revision ownership when a revision repo is configured, writes schedule rows, and transitions the campaign to `scheduled`; update/cancel remain team-scoped through campaign lookup. Publish panel schedule defaults now use current time-relative values (`now + 1 hour`, `now + 7 days`) and disables/prevents scheduling API calls for missing, past, invalid, or end-before-start windows. Validation: schedule API/unit tests passed (10 passed, 1 existing warning); spec and quality reviewers approved; `node --check scripts/smoke-frontend-backend-connection.mjs`, JSX esbuild check for `frontend/CanvasPanels.jsx`, and `git diff --check` passed.

---

## Phase 6: Publish Demo Boundary — Safe Dry-Run or Approved Test Store

**Objective:** Give the showcase a credible publish step without unsafe secret handling or accidental live mutations.

**Files:**
- Verify/modify: `backend/app/services/shopify/publisher.py`
- Verify/modify: `backend/app/api/v1/publishing.py`
- Tests:
  - `backend/tests/unit/test_shopify_publisher.py`
  - `backend/tests/api/test_publishing.py`
- Frontend modify if needed:
  - `frontend/CanvasPanels.jsx`
  - `frontend/CanvasStage.jsx`

**Decision gate before implementation:**
- If Pk/team explicitly approves a safe Shopify test store/theme and credential storage is already configured, implement/request-scoped real adapter.
- Otherwise implement a deterministic `dry_run_demo` publisher mode only, clearly labeled in API response and UI.

**Steps for dry-run demo mode:**
1. Add config flag such as `AIJOLOT_PUBLISH_MODE=dry_run_demo` or use existing settings pattern.
2. In dry-run mode, require the same prerequisites as real publishing:
   - scheduled campaign,
   - active schedule,
   - selected revision,
   - supported placement,
   - generated Liquid/metafield payload.
3. Persist `publish_jobs` with status `published` or `dry_run_published` according to current schema constraints.
4. Return payload preview:
   - theme file keys that would be written,
   - metafield namespace/key/config,
   - published URL/target placeholder,
   - `live_shopify_mutation: false`.
5. Frontend must label result as “Simulación de publicación / dry-run” unless real Shopify confirms.
6. Keep default no-config path fail-closed with `503`.

**Steps for real test-store mode:**
1. Implement request-scoped/decrypted client adapter without logging secrets.
2. Confirm test theme ID and rollback/unpublish path.
3. Use fake adapter tests only; manual live verification is not automated.
4. Never accept Shopify token from frontend headers.

**Validation:**
- `cd backend && . .venv/bin/activate && pytest tests/unit/test_shopify_publisher.py tests/api/test_publishing.py -q`
- Browser: scheduled campaign -> publish -> UI shows dry-run or real status honestly.

**Acceptance Criteria:**
- Publish step can be demonstrated safely.
- There is no accidental live mutation unless explicitly approved.
- UI never claims live publish for dry-run.

**Commit:** `feat: add safe demo publishing path`

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent and passed review after coordinator fixes. Changed `backend/app/core/settings.py`, `backend/app/services/shopify/publisher.py`, `backend/app/api/v1/publishing.py`, `backend/app/agents/skills/shopify-theme-publish/impl.py`, `backend/tests/unit/test_shopify_publisher.py`, `backend/tests/api/test_publishing.py`, `backend/tests/unit/agents/test_shopify_publish_skill.py`, `frontend/CanvasPanels.jsx`, and `frontend/CanvasStage.jsx`. Publishing now fails closed unless `AIJOLOT_PUBLISH_MODE=dry_run_demo` is explicitly set and request team context is available; default REST publishing passes request `team_id` into the service-role dry-run publisher to avoid unscoped/cross-team use. Dry-run publish requires scheduled campaign, active schedule, selected revision matching the schedule revision, supported placement, and generated Liquid/metafield payload; it persists a schema-compatible succeeded publish job with `live_shopify_mutation: false`, theme-file/metafield preview data, target info, and placeholder URL, but does not call Shopify or mark campaign status `published`. Dry-run unpublish fails closed without mutation. Agentic `shopify-theme-publish` skill now requires/passes `team_id`. Frontend labels publish actions and results as “Simulación de publicación / dry-run” and never claims live Shopify publish for dry-run. Validation: publishing API/unit/agent-skill tests passed (18 passed, 1 existing warning); final reviewer approved; `node --check`, JSX esbuild checks for `CanvasPanels.jsx`/`CanvasStage.jsx`, and `git diff --check` passed.

---

## Phase 7: Frontend Demo UX Gap Fixes

**Objective:** Remove visible confusion and stale prototype behavior that could derail the showcase.

**Files:**
- Modify: `frontend/App.jsx`
- Modify: `frontend/Shell.jsx`
- Modify: `frontend/ArtStage.jsx`
- Modify: `frontend/GenerateStage.jsx`
- Modify: `frontend/CanvasStage.jsx`
- Modify: `frontend/CanvasPanels.jsx`
- Modify: `frontend/BrandContextView.jsx`

**Steps:**
1. Resume routing:
   - Add a helper such as `stageForCampaign(campaign, artifacts)`.
   - Draft/no placement -> placement.
   - Brief/art incomplete -> brief/art.
   - Generating/no revision -> generate.
   - Needs review/approved/scheduled/published -> canvas or performance.
2. New campaign creation:
   - Prefer deferring backend creation until intake/brief submission.
   - If not feasible quickly, visibly label empty drafts as `pendiente de brief` and avoid treating them as showcase-ready campaigns.
3. Shell KPIs:
   - Derive basic counts from `CampaignApi.list()` where possible.
   - Label non-live/static KPIs as demo/fallback if not backend-derived.
4. Art stage progression:
   - For UUID/backend mode, block `onAssemble(art)` when art direction save fails.
   - Offer explicit “continuar en modo prototipo” only if desired.
5. Canvas/Generate creative labels:
   - Show backend preview/revision when available from Phase 3.
   - Add explicit local preview badge when using static `Banner` fallback.
6. Schedule dates:
   - Default start/end relative to `new Date()`.
   - Validate start < end and start is future.
7. Brand Context copy:
   - Change visible persistence copy to “se guardan en el backend” or `/api/v1/brands`, not `brands/{id}.md`.

**Validation:**
- Browser manual demo path.
- JSX syntax check using the existing no-build pattern, e.g. the same esbuild/Babel transform command previously used in frontend integration.
- `git diff --check`.

**Acceptance Criteria:**
- Demo presenter can click through without being routed to impossible stages.
- No hardcoded KPI/preview is presented as live backend fact.
- Art/save failures cannot silently lead to broken generation.

**Commit:** `fix: tighten studio demo flow guardrails`

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent and passed review after coordinator fixes. Changed `frontend/App.jsx`, `frontend/Shell.jsx`, `frontend/ArtStage.jsx`, `frontend/GenerateStage.jsx`, `frontend/CanvasStage.jsx`, `frontend/BrandContextView.jsx`, and `frontend/lib.jsx`. Resume routing now inspects backend placement, art direction, and revisions, routes missing-revision campaigns back to Generation instead of Canvas, and keeps published/live campaigns on Performance only when artifacts exist. New campaign no longer creates an empty backend draft immediately and is visibly labeled pending brief. Shell KPIs are backend-derived when available or explicitly demo/fallback-labeled; static fallback draft rows are labeled pending brief. Backend UUID art-save failures block progression, exposing an explicit prototype-only escape hatch; GenerateStage honors `art.prototypeOnly` by entering local prototype mode without calling `GenerationApi.start`. Generate/Canvas creative labels distinguish backend preview/revision from local fallback. Brand context persistence copy now references `/api/v1/brands`/backend, not `brands/{id}.md`. Validation: JSX esbuild checks for all changed frontend files, `python3 scripts/smoke-demo-flow.py`, `node scripts/smoke-frontend-backend-connection.mjs`, and `git diff --check` passed; final reviewer approved.

---

## Phase 8: Browser-Level Smoke and Final Demo Script

**Objective:** Add a fast confidence check that catches the visible UI regressions the current endpoint-only smoke misses.

**Files:**
- Modify/Create: `scripts/smoke-frontend-ui.mjs` or extend `scripts/smoke-frontend-backend-connection.mjs`
- Modify: `docs/architecture/frontend-backend-contract.md`
- Modify/Create: `docs/demo/mvp-showcase-runbook.md`

**Steps:**
1. Keep existing endpoint smoke, but strengthen expected happy path once Phases 1-6 land:
   - generation succeeds,
   - revisions exist,
   - preview/audit exist,
   - approval succeeds,
   - schedule succeeds,
   - publish returns dry-run or real explicit mode.
2. Add lightweight browser/UI smoke if time allows:
   - open static frontend,
   - create/intake campaign,
   - verify campaign appears in list,
   - verify resume routes to correct stage,
   - verify fallback/live labels are visible,
   - verify schedule/publish guardrail messages.
3. Add demo runbook with exact commands:
   - start Supabase/backend/frontend,
   - seed/reset expectations,
   - create demo campaign,
   - generate,
   - approve,
   - schedule,
   - publish dry-run/real,
   - show performance non-live label.
4. Document provider truth table:
   - deterministic agent skills,
   - fake or Gemini image provider,
   - static KG or vector KG if implemented,
   - dry-run or real Shopify.

**Validation:**
- `git diff --check`
- `python3 scripts/smoke-demo-flow.py`
- `node scripts/smoke-frontend-backend-connection.mjs`
- `node scripts/smoke-frontend-ui.mjs` if added
- `cd backend && . .venv/bin/activate && pytest tests/api -q`

**Acceptance Criteria:**
- A fresh developer can run the showcase flow from docs without guessing.
- Smoke tests verify the demo-critical happy path rather than accepting old fail-closed critical-path states.

**Commit:** `test: add mvp demo smoke coverage`

**Progress:** [x] Completed 2026-06-03

Coordinator note: Implemented by fresh subagent and passed review after coordinator fixes. Changed `scripts/smoke-frontend-backend-connection.mjs`, created `scripts/smoke-frontend-ui.mjs`, updated `docs/architecture/frontend-backend-contract.md`, and created `docs/demo/mvp-showcase-runbook.md`. Endpoint smoke now requires a valid generation run, non-empty generation events, KG/research context, and consistent preview/audit/revision persistence semantics: invalid 200 preview/audit responses fail the smoke, persisted revisions require preview and audit, and persistence-only optional routes must either succeed or fail closed with 404/409/422/503. UI static smoke checks demo-critical frontend labels/guardrails for API path/auth, resume/create routing, backend/fallback labels, generation fail-closed states, backend creative vs local fallback, approval/schedule/publish dry-run guardrails, and non-live performance labels. Runbook includes exact setup/smoke/backend/frontend/browser commands and provider truth table. Validation: `git diff --check`, `node scripts/smoke-frontend-ui.mjs`, `python3 scripts/smoke-demo-flow.py`, `node scripts/smoke-frontend-backend-connection.mjs`, and backend API tests passed (110 passed, 1 existing warning); final reviewer approved.

---

## Phase 9: Optional Post-Critical Enhancements Only If Time Remains

Do not start these until Phases 1-8 pass.

**Progress:** [-] Skipped/deferred 2026-06-03

Coordinator note: Phases 1-8 now cover the critical MVP showcase path with full validation. These enhancements remain explicitly post-critical/deferred so the demo stays stable: registry endpoints, live analytics ingestion, vector KG/live provider work, and any real Shopify mutation require separate scope/configuration and are not needed for the few-hours MVP showcase.

### 9A: Read-only model/style/grid registries

**Goal:** Replace local frontend presets with backend-managed read-only demo registries.

**Candidate files:**
- `backend/app/api/v1/presets.py`
- `backend/app/schemas/presets.py`
- `frontend/ModelBank.jsx`
- `frontend/ArtStage.jsx`

**Keep simple:** seeded read-only endpoints are enough for MVP. Avoid uploads/model generation unless needed.

### 9B: Learning memory endpoint

**Goal:** Aggregate existing performance insights/proposals into a team/campaign memory feed with provenance.

**Candidate endpoint:**
- `GET /api/v1/teams/{team_id}/learning-memory`

### 9C: Live Shopify resource sync

**Goal:** Explicitly sync Shopify products/collections/pages into the cache if safe credentials/test store are approved.

**Defer by default:** current seeded/cache resource flow is sufficient for demo if labeled.

### 9D: Live analytics ingestion

**Goal:** Add source-labeled snapshots from a real provider.

**Defer by default:** preserve non-live labels.

---

## Full MVP Acceptance Criteria

The MVP is showcase-ready when all must-have checks pass:

1. Campaign can be created/intaken from frontend with a backend UUID.
2. Placement saves to backend and can be fetched.
3. Brief/art direction persist; save failures are visible and block backend-mode progression.
4. Generation succeeds from frontend and backend API.
5. Generation events reflect deterministic agentic skill execution with provenance labels.
6. Selected revision exists after generation.
7. Preview HTML and audit report are available after generation.
8. Canvas renders backend preview/revision when available.
9. Approval thread works in local demo and campaign transitions to `approved`.
10. Schedule works after approval and selected revision.
11. Publish step returns either real approved test-store success or explicit dry-run success with no live mutation claim.
12. Performance remains labeled non-live unless real analytics exists.
13. Shell resume routing and KPI labels do not mislead demo users.
14. Smoke tests no longer accept critical-path generation/revision/approval/schedule failures as expected once fixed.
15. Documentation/runbook describes exactly which parts are real, deterministic, dry-run, or deferred.

---

## Risks and Tradeoffs

- Full ADK asynchronous HITL/resume may be too large for the remaining time. The deterministic agentic adapter is the pragmatic MVP bridge.
- Real Shopify publish is risky without explicit safe store/theme approval. Dry-run publish is safer and still lets the demo show controlled Liquid/metafield payloads.
- Real Gemini/Gemini Image calls could introduce latency/provider instability. Keep deterministic fake/provider fallback as default and expose mode labels.
- If local Supabase schema/runtime differs from tests, prioritize a migration-shaped integration regression for generation events/artifacts.
- Avoid broad refactors. The demo-critical path should be implemented through existing services/routes/components.

---

## Self-Review Loop

### Pass 1: Against `frontend-assumed-backend-gaps.md`

Covered all 13 listed gaps. Classified backend import as done, optional registries/sync/analytics/memory as deferrable, and moved critical generation/revision/approval/schedule/publish into ordered phases.

### Pass 2: Against current agentic function state

Added a dedicated phase to wire deterministic agent skills into generation artifacts. Explicitly documented that current generation endpoints are facade-only and that full ADK/HITL/resume is not yet showcase-safe.

### Pass 3: Against visible frontend/demo gaps

Added frontend UX phase for resume routing, premature draft creation, hardcoded KPIs, static creative fallback labels, art save blocking, stale schedule defaults, and Brand Context copy.

### Pass 4: Against test/smoke gaps

Added browser/UI smoke and strengthened endpoint smoke expectations so old fail-closed critical path states do not remain accepted after implementation.

### Confidence statement

After these review passes, this plan covers the missing critical path for a fully showcaseable MVP without hiding provider/shopify/live-data limitations. The remaining optional gaps are explicitly deferred and safe to leave out of the hackathon demo if labels are truthful.

---

## Do Not Execute Yet

This plan was requested as planning only. Start implementation only after Pk approves the scope and chooses the publish mode:

1. `dry_run_demo` publish for safe showcase, or
2. real Shopify test-store publish with explicit approved credentials/theme boundary.
