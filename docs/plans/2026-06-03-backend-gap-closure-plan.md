# Backend Gap Closure Plan for Banner Studio End-to-End Demo

> **For Hermes:** This is a planning document only. Do not execute this plan until the team reviews ownership and confirms which backend pieces are already being handled elsewhere.

**Goal:** Close backend gaps needed for the now-integrated Banner Studio frontend to run a real local end-to-end flow from campaign creation through generation, approval, scheduling, and safe Shopify publishing.

**Architecture:** Keep `/api/v1` as the canonical frontend contract. Preserve fail-closed behavior for real providers, but make the deterministic local/Supabase demo path complete. Add schema-aligned tests before implementation changes. Live Shopify/Gemini/analytics paths must remain opt-in and safe.

**Tech Stack:** FastAPI, Pydantic v2, Supabase/Postgres, pytest/httpx, static React frontend consumers.

---

## Review Gate Before Execution

Before implementing, ask the team:

1. Is anyone already fixing the generation event `output_summary` Supabase/runtime failure?
2. Should the demo use deterministic fake generation only, or real Gemini when keys are present?
3. Who owns approval/reviewer data: seeded demo users, Supabase Auth users, or a separate identity source?
4. Should Shopify publish be implemented now, or remain fail-closed until credential storage is finalized?
5. Are model-bank/style-grid/memory/live-sync/live-analytics in MVP scope or post-demo scope?
6. Is a live Shopify test store/theme available and explicitly approved for mutation?

Do not execute tasks involving Shopify mutation without explicit approval and a safe test store/theme.

---

## Phase A: Fix generation events and revision creation in local Supabase runtime

**Objective:** Browser/static frontend generation should create a backend generation run, ordered events, selected revision, variants, preview HTML, and audit report without 500s in local Supabase.

**Files likely involved:**
- `backend/app/services/banners/generation_run_service.py`
- `backend/app/db/repositories/generation_events.py`
- `backend/app/services/banners/revision_service.py`
- `backend/app/services/banners/html_renderer.py`
- `backend/app/services/shopify/liquid_payload_builder.py`
- `backend/tests/api/test_generation.py`
- `backend/tests/unit/test_generation_run_service.py`
- `supabase/migrations/*` only if schema is genuinely wrong; prefer fixing payload if schema constraint is correct.

**Tasks:**
1. Reproduce the runtime 500 against local Supabase using a test that executes against migration-shaped schema or a focused local integration test.
2. Write a regression test asserting every `generation_events` insert has non-null `output_summary`.
3. Fix deterministic event payload generation to satisfy schema.
4. Ensure generation success creates or links:
   - generation run,
   - generation events,
   - campaign revision,
   - layout variants A/B/C,
   - segment variants if expected,
   - selected revision/variant,
   - preview HTML,
   - audit report.
5. Update smoke script expectations from fail-closed generation 500 to successful generation once fixed.
6. Verify browser/static frontend generation advances only after backend success.

**Validation:**
- `cd backend && . .venv/bin/activate && pytest tests/api/test_generation.py tests/unit/test_generation_run_service.py -q`
- `python3 scripts/smoke-demo-flow.py`
- `node scripts/smoke-frontend-backend-connection.mjs`

---

## Phase B: Wire approval/comment/refinement services for local Supabase demo

**Objective:** Canvas approval/comment/refinement actions should use backend state by default in local Supabase instead of returning 503 unavailable.

**Files likely involved:**
- `backend/app/services/approvals/approval_service.py`
- `backend/app/services/approvals/comment_service.py`
- `backend/app/api/v1/approvals.py`
- `backend/app/db/repositories/*approval*`
- `backend/app/db/repositories/*comment*`
- `supabase/seed.sql`
- `backend/tests/api/test_approvals.py`

**Tasks:**
1. Inspect existing repositories/schema for approval threads, reviewers, comments, refinement requests.
2. Add or complete `configured_service_for_team(...)` for approvals/comments using Supabase service-role client and request team context.
3. Seed demo reviewer user IDs/roles if required.
4. Ensure approval request can be created for generated selected revision.
5. Ensure all-reviewer approval transitions campaign status to `approved`.
6. Ensure request-changes creates refinement request and transitions status to `changes_requested`.
7. Ensure comments and pin resolution are persisted and team/campaign scoped.
8. Keep non-Supabase/no-config paths fail-closed or explicitly demo-only, not globally shared.

**Validation:**
- `cd backend && . .venv/bin/activate && pytest tests/api/test_approvals.py -q`
- Add/extend tests for local configured service path.
- Browser: Canvas shows backend approval mode after generation.

---

## Phase C: Complete refinement/regeneration path

**Objective:** A backend refinement request from Canvas should regenerate a new revision, preserve old revision, supersede selected variant/revision correctly, and refresh frontend-visible revision list.

**Files likely involved:**
- `backend/app/services/banners/revision_service.py`
- `backend/app/api/v1/generation.py`
- `backend/app/services/approvals/*`
- `backend/tests/api/test_generation.py`
- `backend/tests/unit/test_revision_service.py`

**Tasks:**
1. Write tests for request changes -> refinement request -> regenerate.
2. Ensure regeneration creates a new generation run and revision.
3. Ensure previous revisions remain accessible.
4. Ensure selected revision/variant is updated only after successful regeneration.
5. Ensure addressed comments are marked/resolved consistently.

**Validation:**
- Focused revision/regeneration tests.
- Frontend Canvas refinement action shows backend success and updated variant/revision controls.

---

## Phase D: Make schedule happy path reachable

**Objective:** After backend approval and selected revision, `POST /api/v1/campaigns/{id}/schedule` should succeed in local Supabase and be visible in frontend.

**Files likely involved:**
- `backend/app/services/banners/schedule_service.py`
- `backend/app/api/v1/schedules.py`
- `backend/app/db/repositories/schedules.py`
- `backend/tests/api/test_schedules.py`
- `supabase/seed.sql` if demo data needed.

**Tasks:**
1. Add an end-to-end backend test: generated campaign -> approve all -> schedule.
2. Verify schedule requires `approved` or `scheduled` status and selected revision.
3. Verify schedule persists row and updates campaign status to `scheduled`.
4. Verify update/cancel paths with team scoping.
5. Verify frontend smoke can schedule after approved selected revision.

**Validation:**
- `cd backend && . .venv/bin/activate && pytest tests/api/test_schedules.py -q`
- `node scripts/smoke-frontend-backend-connection.mjs` after updating expected happy path.

---

## Phase E: Safe Shopify publisher adapter and publish/unpublish happy path

**Objective:** Publish scheduled campaign config to a controlled Shopify test store/theme only when safe credentials and explicit target are configured.

**Files likely involved:**
- `backend/app/services/shopify/client.py`
- `backend/app/services/shopify/publisher.py`
- `backend/app/services/shopify/theme_files.py`
- `backend/app/services/shopify/metafields.py`
- `backend/app/api/v1/publishing.py`
- `backend/tests/unit/test_shopify_publisher.py`
- `backend/tests/api/test_publishing.py`

**Tasks:**
1. Confirm approved test store/theme and credential storage approach with team.
2. Implement request-scoped/decrypted Shopify client adapter; do not read/print secrets in route logs or frontend.
3. Keep default no-credential path fail-closed with 503.
4. Ensure publishing requires `scheduled`, active schedule, selected revision, valid store/theme.
5. Install/update controlled Liquid/theme files idempotently.
6. Publish/unpublish campaign config through configured metafield namespace/key.
7. Reject unsupported search-result placement unless implemented.
8. Record publish_jobs with idempotency, response payload, error payload, and rollback safety.
9. Add fake Shopify adapter tests; do not make live Shopify calls in automated tests.
10. Add a manual-only live Shopify verification checklist.

**Validation:**
- `cd backend && . .venv/bin/activate && pytest tests/unit/test_shopify_publisher.py tests/api/test_publishing.py -q`
- Manual approved test-store publish/unpublish only after explicit approval.

---

## Phase F: Optional Shopify resource sync

**Objective:** Replace seeded resource cache with explicit live/manual sync for products, collections, pages, and supported search/placement targets.

**Tasks:**
1. Add sync endpoint/job that uses safe Shopify adapter.
2. Upsert resources idempotently into cache.
3. Track `synced_at`, source, and stale status.
4. Frontend should surface cached-vs-live/stale labels.

**Validation:**
- Fake Shopify adapter tests.
- Seed/local fallback remains deterministic.

---

## Phase G: Optional UI-support registry endpoints

**Objective:** Replace remaining local frontend presets with backend/team/brand scoped data where product wants central management.

**Candidate endpoints:**
- `GET /api/v1/brands/{brand_id}/model-assets`
- `POST /api/v1/brands/{brand_id}/model-assets`
- `GET /api/v1/brands/{brand_id}/art-style-presets`
- `GET /api/v1/stores/{store_id}/layout-presets`
- `GET /api/v1/teams/{team_id}/learning-memory`

**Tasks:**
1. Confirm with team which presets are MVP vs future.
2. Add schema/migrations only for chosen registries.
3. Preserve frontend fallback presets if endpoints unavailable.

---

## Phase H: Optional live analytics ingestion

**Objective:** Provide real performance metrics when explicitly configured, without mislabeling seed/manual data.

**Tasks:**
1. Define source: Shopify analytics, GA, or another provider.
2. Add ingestion job/endpoints with explicit provenance.
3. Store snapshots with `source = live_analytics` only when truly live.
4. Frontend should switch label to live only when `live_analytics: true`.

---

## Team Checkpoint Questions

Use this list in team discussion:

- Which phases are already assigned to backend teammates?
- Which phases are required for the demo versus post-demo?
- Do we have a safe Shopify test store/theme and approval to mutate it?
- Should browser/static frontend smoke expect generation success after Phase A?
- Should approval users be seeded demo users or come from Supabase Auth?
- Should model/style/grid presets stay local until Next.js migration?

## Do Not Execute Yet

This plan is intentionally not executed in the frontend integration session. It exists so the team can confirm ownership and missing backend scope before implementation.
