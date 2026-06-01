# Banner Creator MVP Implementation Plan

> **For Hermes:** Use `subagent-driven-development` to implement this plan task-by-task. Start every implementation task from `main` on a new branch. Do not re-create files/features already present unless the task explicitly says to refactor or replace them.

**Last updated:** 2026-05-29, after merging the team's frontend, campaign-object, chatbox, and ADK scaffold work.

**Goal:** Build a Shopify-focused agentic banner creator that lets marketing users select placement, write a campaign brief, generate banner art/copy with Google ADK + Gemini, request team review/comments, approve, schedule, and publish approved banners to a Shopify store.

**Architecture:** FastAPI owns the backend API, state transitions, Supabase persistence/storage/auth integration, Google ADK orchestration, Gemini generation, audit gates, scheduling, and Shopify publishing. The current frontend under `frontend/` is a static React prototype and is now the UX/product contract; future Next.js + Tailwind migration is frontend-owned. Shopify storefront rendering uses a controlled Online Store 2.0 Liquid section/snippet that reads structured campaign config from Shopify metafields/metaobjects and keeps banner copy as HTML/CSS/Liquid-rendered text, not baked into generated images.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, Google ADK, google-genai/Gemini, Supabase Postgres/Auth/Storage/pg_cron/pg_net, Shopify Admin GraphQL API, Jinja2/Liquid, Pillow/WebP/AVIF, pytest/httpx/respx, current static React prototype, future Next.js + Tailwind.

---

## 1. Current Repository Reality

### 1.1 Existing backend/API work that must not be re-done

The team has already added these backend artifacts on `main`:

- `backend/pyproject.toml`
  - Includes FastAPI, uvicorn, Pydantic, PyYAML, SSE support, Google ADK, google-genai, Supabase client, Pillow/AVIF, Jinja2, validators, httpx, tenacity, pytest tooling.
- `backend/app/main.py`
  - FastAPI app.
  - Dev CORS.
  - Routers included for `brands`, `intake`, and `campaigns`.
  - `GET /health` exists.
- Brand endpoints already existed before the latest merge:
  - `GET /brands`
  - `GET /brands/{brand_id}`
  - `PUT /brands/{brand_id}`
  - Still Markdown/file-backed through `brands/{id}.md`.
- New campaign/intake endpoints now exist:
  - `POST /campaigns/intake`
  - `GET /campaigns/{campaign_id}`
  - `PATCH /campaigns/{campaign_id}`
- New campaign objects now exist:
  - `backend/app/schemas/campaign.py`
  - `StructuredBrief`
  - `CampaignMessage`
  - `Campaign`
  - `IntakeRequest`
  - `BriefPatch`
- New deterministic/in-memory campaign store now exists:
  - `backend/app/services/campaign_store.py`
  - rule-based brief extraction
  - in-memory campaigns
  - in-memory campaign messages
  - SSE-compatible intake response flow
- Tests now exist:
  - `backend/tests/api/test_intake.py`
  - `backend/tests/api/test_campaigns.py`
  - `backend/tests/api/test_brands.py`

Conclusion: the plan must not ask us to recreate a FastAPI skeleton, campaign schema, root-level intake SSE, or basic campaign GET/PATCH from scratch. Those are now baseline work to preserve and evolve.

### 1.2 Existing ADK/agentic scaffold that must not be re-done

The team has scaffolded the agentic stack:

- `backend/app/agents/state.py`
  - `BannerSessionState`
  - in-graph `Campaign`, `Variant`, `Concept`, `BannerAssets`, `AuditReport`, `HITLDecision`, `PublishResult`
- `backend/app/agents/graph.py`
  - 12-node topology and `NodeSpec` list:
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
- `backend/app/agents/coordinator.py`
  - Coordinator placeholder with model env lookup.
- `backend/app/workflows/banner_creation.py`
  - `start_session()` implemented.
  - `run_to_audit()` and `resume_after_hitl()` intentionally `NotImplementedError`.
- `backend/adk_agents/banner_coordinator/agent.py`
  - Minimal ADK `root_agent` for `adk web` intake-only demo.
- ADK internal tools scaffold exists under `backend/app/agents/tools/`:
  - `gemini_text.py`
  - `nano_banana_image.py`
  - `image_optim.py`
  - `html_render.py`
  - `liquid_render.py`
  - `audit_w3c.py`
  - `audit_lighthouse.py`
  - `audit_schema.py`
  - `audit_log.py`
  - `brand_fs.py`
  - `kg.py`
  - `shopify.py`
- ADK skills scaffold exists under `backend/app/agents/skills/` with `SKILL.md` + `impl.py` placeholders.
- Sub-agent scaffold exists:
  - `backend/app/agents/sub_agents/creative_director.py`
  - `backend/app/agents/sub_agents/auditor.py`
- Prompt files exist:
  - `backend/app/agents/prompts/*.md`
- KG seed README exists:
  - `docs/kg_seed/README.md`

Conclusion: the 12-node graph, state models, skills index, prompts, internal tools, and ADK web intake-only entrypoint are in scope and match our plan. We should integrate with them rather than creating parallel `agents/nodes/*` modules unless we intentionally migrate the scaffold.

### 1.3 Existing Supabase work

The project already has local Supabase defined by:

- `supabase/config.toml`
- `supabase/migrations/20260528190000_initial_schema.sql`
- `supabase/seed.sql`
- `.env.example`

Local ports:

- API: `http://127.0.0.1:55321`
- Studio: `http://127.0.0.1:55323`
- DB: `127.0.0.1:55322`
- Mailpit: `http://127.0.0.1:55324`

Verified local DB extensions from the running project instance:

- `pg_cron` installed
- `pg_net` installed

Storage buckets:

- `brand-assets`
- `campaign-assets`
- `rendered-previews`

Conclusion: the implementation plan should not include an initial schema task as if the DB does not exist. Future DB work should be additive migrations only.

### 1.4 Existing frontend work

The frontend is currently a full static React 18 UMD/Babel prototype, not a Next.js app yet. It lives under `frontend/` and includes the full UX flow:

- Dashboard/shell
- Brand context
- Placement
- Brief/chat
- Art direction
- Generation pipeline
- Canvas/review/approval/schedule/publish
- Performance/evolutionary memory

Reference doc:

- `docs/architecture/frontend-template-deep-dive.md`

Conclusion: backend APIs should support this UX contract. Do not rewrite or migrate frontend as part of backend tasks unless explicitly requested.

### 1.5 Verification limitation found while updating this plan

Attempted test commands:

```bash
cd backend
pytest -q
python3 -m pytest -q
```

Both failed because pytest is not installed in the currently active Python environment. This is not a code failure; it is an environment/setup gap. Task 0 below makes backend environment setup and test verification explicit.

---

## 2. Scope Decisions

### In scope

- Shopify stores only.
- FastAPI backend.
- Supabase Auth/Postgres/Storage.
- Google ADK + Gemini agentic workflow.
- Current static React prototype support.
- Future Next.js + Tailwind compatibility, but not our current implementation responsibility.
- Brand context API and storage.
- Campaign intake and structured brief.
- Campaign placement.
- Campaign catalog snapshots.
- Art direction persistence.
- Generation run tracking and progress events.
- ADK 12-node graph execution up to audit and HITL handoff.
- Team approval/comments with all-reviewers approval policy.
- Scheduling with active start/end window.
- Optional pg_cron-compatible due-publish records.
- Shopify publishing through Admin GraphQL and controlled Liquid section/snippet.
- Performance/audit/optimization memory schema support.

### Out of scope unless explicitly added

- Full Shopify OAuth app flow.
- Multi-platform ecommerce.
- Payment/subscription.
- True real-time collaborative editing.
- Fully generic arbitrary DOM injection into unknown Shopify themes.
- Live analytics ingestion unless needed for demo.
- Full frontend migration to Next.js + Tailwind.

---

## 3. Implementation Rules Going Forward

1. Start every task from `main` on a new branch.
2. Do not duplicate existing root routes while adding `/api/v1`; wrap or migrate them.
3. Do not create a second campaign model tree that conflicts with `backend/app/schemas/campaign.py` or `backend/app/agents/state.py`.
4. Do not create a second ADK topology that conflicts with `backend/app/agents/graph.py`.
5. Existing `NotImplementedError` scaffolds are not bugs by themselves; they are planned implementation seams. Each must be replaced in the task that owns it.
6. Do not rely on in-memory stores past the tasks that explicitly allow them.
7. Every allowed temporary gap must appear in the carry-over ledger in Section 8.
8. When schema changes are needed, add a new migration under `supabase/migrations/`; do not edit local DB manually.
9. Keep demo reliability first: if an external provider is unstable, use explicit fake/deterministic providers and label them.

---

## 4. Status Model

Primary path:

```text
draft
  -> placement_selected
  -> brief_ready
  -> art_direction_ready
  -> generating
  -> audit_pending
  -> needs_review
  -> changes_requested
  -> generating
  -> audit_pending
  -> needs_review
  -> approved
  -> scheduled
  -> publishing
  -> published
```

Failure/escalation paths:

```text
generating -> failed -> draft or generating
audit_pending -> audit_retrying -> audit_pending
audit_pending -> audit_escalated -> needs_review
publishing -> failed -> scheduled or publishing
scheduled -> cancelled
published -> archived
```

Rules:

- Only campaigns with placement, brief, and art direction can start generation.
- Publishing must never happen before HITL approval.
- MVP approval policy requires all assigned reviewers to approve.
- Scheduling requires approved campaign status.
- Publishing requires scheduled campaign status unless an explicit publish-now path first creates a valid schedule/window.

---

## 5. Updated Implementation Plan

### Task 0: Local backend environment and baseline verification

**Status:** Completed on 2026-05-29 in branch `feature/backend-mvp-implementation`.

**Completion note:** Added explicit setuptools package discovery for `app*` and `adk_agents*` in `backend/pyproject.toml`, created backend `.venv` with Python 3.11.15, installed `pip install -e ".[dev]"`, and verified `pytest -v` passes with 12 tests.

**Goal:** Make the current merged work runnable and testable locally before adding more code.

**Expected result:** Backend dependencies are installed in a local virtual environment and current tests can run.

**Files:**

- Modify only if needed: `README.md`
- Modify only if needed: `backend/pyproject.toml`

**Steps:**

```bash
git checkout main
git pull --ff-only
git checkout -b chore/backend-baseline-verification
cd backend
python3.11 -m venv .venv || python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

If Python 3.11 is not available locally, install it or document the Python version actually used.

**Verification:**

- `pytest -v` runs.
- Current tests pass or any real failures are documented and fixed before feature work.

**Carry-over bugs/gaps:** none. Do not proceed with implementation while tests cannot run.

---

### Task 1: Add shared settings and dependency boundaries without duplicating existing app setup

**Status:** Completed on 2026-05-29 in branch `feature/backend-mvp-implementation`.

**Completion note:** Added `app.core.settings`, `app.core.dependencies`, and lazy Supabase client factory. Settings now cover Supabase/Gemini/Google/Shopify/app behavior env vars, use `SecretStr` for secrets, defer required-secret validation to `require_*` methods, ignore blank env vars safely, and provide FastAPI-overridable dependency boundaries. Verified with `pytest tests/unit/test_settings.py -v` and full `pytest -v`.

**Goal:** Centralize env/settings and client dependencies while preserving existing `app.main`, routers, and tests.

**Expected result:** Settings can be loaded for Supabase, Gemini, Shopify, and app behavior. External clients are created behind injectable boundaries, not at import time.

**Files:**

- Create: `backend/app/core/settings.py`
- Create: `backend/app/core/dependencies.py`
- Create: `backend/app/services/supabase/client.py`
- Modify: `backend/app/main.py` only if dependency wiring needs app state.
- Modify: `.env.example` only if missing variables.
- Test: `backend/tests/unit/test_settings.py`

**Do not redo:**

- Do not recreate `backend/pyproject.toml` from scratch.
- Do not recreate the FastAPI app.
- Do not remove existing `brands`, `intake`, or `campaigns` routers.

**Verification:**

```bash
cd backend
. .venv/bin/activate
pytest tests/unit/test_settings.py -v
pytest -v
```

**Carry-over bugs/gaps:**

- Existing brand and campaign stores may remain file/in-memory backed after this task.
- They must be moved to Supabase in Tasks 2 and 4.

---

### Task 2: Add `/api/v1` router while preserving current prototype routes

**Status:** Completed on 2026-05-29 in branch `feature/backend-mvp-implementation`.

**Completion note:** Added canonical `/api/v1` router modules that reuse existing brand/intake/campaign route logic, registered the v1 router in `app.main`, documented the current compatibility and v1 API contract, and added contract tests for root compatibility plus v1 brand/intake/campaign routes. Verified with `pytest tests/api/test_api_v1_contract.py -v` and full `pytest -v`.

**Goal:** Create the stable canonical API namespace without breaking the static frontend prototype.

**Expected result:** Existing root routes still work, and equivalent `/api/v1` routes are available for new integration work.

**Files:**

- Create: `backend/app/api/v1/router.py`
- Create or move wrappers:
  - `backend/app/api/v1/brands.py`
  - `backend/app/api/v1/campaigns.py`
  - `backend/app/api/v1/intake.py`
- Modify: `backend/app/main.py`
- Create: `docs/architecture/api-contract.md`
- Test: `backend/tests/api/test_api_v1_contract.py`

**Existing work to reuse:**

- `backend/app/api/brands.py`
- `backend/app/api/intake.py`
- `backend/app/api/campaigns.py`
- `backend/app/schemas/campaign.py`

**Verification:**

```bash
cd backend
pytest tests/api/test_api_v1_contract.py -v
pytest -v
```

Manual:

- `GET /health` works.
- `POST /campaigns/intake` still works.
- `POST /api/v1/campaigns/intake` works or documented canonical equivalent exists.

**Carry-over bugs/gaps:**

- Root-level compatibility routes may remain until static frontend migration is complete.
- Fix/decision point: Task 18.

---

### Task 3: Move brand context runtime storage to Supabase

**Status:** Completed on 2026-05-29 in branch `feature/backend-mvp-implementation`.

**Completion note:** Added Supabase repositories for `brand_contexts`/`brand_assets`, a brand service with Supabase-first runtime storage and Markdown fallback/import, safe Markdown importer, `POST /brands/import`, hyphenated brand slug support, repository payload filtering to actual schema columns, centralized brand team settings, deterministic fallback tests, and a skippable live Supabase integration test. Verified with targeted brand tests and full `pytest -v` (`42 passed, 1 skipped`). Auth for write endpoints remains a planned Task 19 concern.

**Goal:** Replace Markdown file-backed runtime brand storage with Supabase-backed `brand_contexts`/`brand_assets`, while preserving Markdown files as seed/import sources.

**Expected result:** Brand endpoints return Supabase data; Markdown import remains available for demo/versioned seed content.

**Files:**

- Modify: `backend/app/services/brand_store.py`
- Create: `backend/app/db/repositories/brand_contexts.py`
- Create: `backend/app/db/repositories/brand_assets.py`
- Create: `backend/app/services/brands/brand_service.py`
- Create: `backend/app/services/brands/markdown_importer.py`
- Modify: `backend/app/api/brands.py`
- Modify or create: `backend/app/api/v1/brands.py`
- Modify: `backend/app/schemas/brand.py` only as needed.
- Test: `backend/tests/unit/test_brand_markdown_importer.py`
- Test: `backend/tests/api/test_brands.py`
- Test: `backend/tests/integration/test_brand_context_repository.py`

**Do not redo:**

- Do not delete the current brand schema unless replacing it with compatible fields.
- Do not remove seed Markdown files.

**Verification:**

```bash
cd backend
pytest tests/unit/test_brand_markdown_importer.py -v
pytest tests/api/test_brands.py -v
pytest -v
cd ..
supabase db reset
```

**Carry-over bugs/gaps:**

- PDF/Figma/brandbook extraction can be partial/mock if clearly labeled.
- Fix/decision point: Task 21.

---

### Task 4: Move campaign/intake runtime storage from in-memory to Supabase

**Status:** Completed on 2026-05-30 in branch `feature/backend-mvp-implementation`.

**Completion note:** Added Supabase repositories for `campaigns` and `campaign_messages`, a `CampaignService` with Supabase-first persistence and local in-memory fallback only when Supabase is not configured, status transition helpers, `/api/v1/campaigns` create/list/get/patch semantics through the shared router, persisted intake messages, non-editable campaign protection, partial Supabase config fail-fast behavior, live Supabase integration opt-in via `RUN_LIVE_SUPABASE_TESTS=1`, and route-level Task 19 auth/scoping TODOs. Verified with targeted Task 4 tests and full `pytest -v` (`49 passed, 2 skipped`). Auth/request-scoped tenancy remains intentionally deferred to Task 19.

**Goal:** Keep the team's campaign/intake behavior while persisting campaigns and messages in Supabase.

**Expected result:** `POST /campaigns/intake`, `GET /campaigns/{id}`, and `PATCH /campaigns/{id}` survive process restarts and use `campaigns`/`campaign_messages` tables.

**Files:**

- Modify: `backend/app/services/campaign_store.py`
- Create: `backend/app/db/repositories/campaigns.py`
- Create: `backend/app/db/repositories/campaign_messages.py`
- Create: `backend/app/services/banners/campaign_service.py`
- Create: `backend/app/services/banners/status_machine.py`
- Modify: `backend/app/api/intake.py`
- Modify: `backend/app/api/campaigns.py`
- Modify or create: `backend/app/api/v1/intake.py`
- Modify or create: `backend/app/api/v1/campaigns.py`
- Test: `backend/tests/unit/test_campaign_status_machine.py`
- Test: `backend/tests/api/test_intake.py`
- Test: `backend/tests/api/test_campaigns.py`
- Test: `backend/tests/integration/test_campaign_repository.py`

**Existing work to reuse:**

- `StructuredBrief`
- `CampaignMessage`
- `Campaign`
- deterministic `extract_into()` behavior
- SSE response shape from `POST /campaigns/intake`

**Implementation notes:**

- Keep deterministic extractor as fallback/test path.
- Preserve SSE event shape:
  - `token`
  - `done`
- Add list/create/detail semantics under `/api/v1` as needed by dashboard:
  - `POST /api/v1/campaigns`
  - `GET /api/v1/campaigns`
  - `GET /api/v1/campaigns/{campaign_id}`
  - `PATCH /api/v1/campaigns/{campaign_id}`

**Verification:**

```bash
cd backend
pytest tests/api/test_intake.py -v
pytest tests/api/test_campaigns.py -v
pytest tests/integration/test_campaign_repository.py -v
pytest -v
```

Manual:

- Start backend, create campaign through intake, restart backend, retrieve same campaign.

**Carry-over bugs/gaps:**

- The intake may still use deterministic extraction after this task.
- Gemini-powered extraction must be connected in Task 9.

---

### Task 5: Implement store and Shopify resource cache APIs

**Status:** Completed on 2026-05-30 in branch `feature/backend-mvp-implementation`.

**Completion note:** Added frontend-safe store/resource schemas, Supabase repositories for `stores` and `shopify_resource_cache`, a cache-only `ShopifyResourceService` with seeded fallback, fail-closed Supabase team scoping, recursive metadata secret redaction, UUID store route validation, and `/api/v1/stores` endpoints for store list/detail and selectable cached/virtual Shopify resources. Verified with Task 5 tests and full `pytest -v` (`63 passed, 2 skipped`). Live Shopify sync remains intentionally deferred to Task 17/21.

**Goal:** Provide store/catalog data required by placement and brief stages using seeded `stores` and `shopify_resource_cache` data first.

**Expected result:** Frontend can list stores and selectable Shopify resources without live Shopify calls.

**Files:**

- Create: `backend/app/schemas/stores.py`
- Create: `backend/app/db/repositories/stores.py`
- Create: `backend/app/db/repositories/shopify_resource_cache.py`
- Create: `backend/app/services/shopify/resource_service.py`
- Create: `backend/app/api/v1/stores.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/api/test_stores.py`
- Test: `backend/tests/unit/test_shopify_resource_service.py`

**Endpoints:**

- `GET /api/v1/stores`
- `GET /api/v1/stores/{store_id}`
- `GET /api/v1/stores/{store_id}/shopify/resources?resource_type=collection|product|page|search`

**Verification:**

```bash
cd backend
pytest tests/api/test_stores.py -v
pytest tests/unit/test_shopify_resource_service.py -v
pytest -v
```

**Carry-over bugs/gaps:**

- Live Shopify sync can remain unimplemented if demo uses seeded resources.
- Fix/decision point: Task 17 or Task 21.

---

### Task 6: Implement placement registry and campaign placement APIs

**Status:** Completed on 2026-05-30 in branch `feature/backend-mvp-implementation`.

**Completion note:** Added placement schemas, seeded/Supabase placement type repositories, campaign placement repository, placement service, `/api/v1` placement endpoints, validation for existing-section and new-section modes, cached/virtual target validation, campaign placement save/read, UUID validation, non-resource target guardrails, and Task 19 auth/scoping TODOs. Verified with Task 6 tests and full `pytest -v` (`81 passed, 2 skipped`). Search-result placement validation is supported; actual publish support remains deferred to Task 17.

**Goal:** Power the frontend placement stage using seeded placement types and persist selected placement details.

**Expected result:** Campaign placement can be validated and saved, including existing-section mode and injected-section layout JSON.

**Files:**

- Create: `backend/app/schemas/placements.py`
- Create: `backend/app/db/repositories/placement_types.py`
- Create: `backend/app/db/repositories/campaign_placements.py`
- Create: `backend/app/services/banners/placement_service.py`
- Create: `backend/app/api/v1/placements.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/unit/test_placement_service.py`
- Test: `backend/tests/api/test_placements.py`

**Endpoints:**

- `GET /api/v1/stores/{store_id}/placement-types`
- `GET /api/v1/stores/{store_id}/placement-types/{placement_type_key}/targets`
- `POST /api/v1/placements/validate`
- `POST /api/v1/campaigns/{campaign_id}/placement`
- `GET /api/v1/campaigns/{campaign_id}/placement`

**Verification:**

```bash
cd backend
pytest tests/unit/test_placement_service.py -v
pytest tests/api/test_placements.py -v
pytest -v
```

**Carry-over bugs/gaps:**

- Search-result placement can validate/save before publish support exists.
- Fix/decision point: Task 17. It must either publish correctly or be blocked with a clear unsupported-for-publish error.

---

### Task 7: Implement catalog snapshot APIs

**Status:** Completed on 2026-05-30 in branch `feature/backend-mvp-implementation`.

**Completion note:** Added catalog snapshot schemas, Supabase/in-memory catalog repositories, catalog snapshot service, and `/api/v1/campaigns/{campaign_id}/catalog-snapshot` POST/GET endpoints. Snapshots are sourced only from cached/seeded Shopify resources, include reproducible item context with safe metadata redaction and immutable store context, preserve deterministic ordering on create/get, and compensate cleanup on item-insert failure. Verified with Task 7 tests and full `pytest -v` (`90 passed, 2 skipped`).

**Goal:** Freeze product/catalog context at campaign generation time.

**Expected result:** A campaign can store and retrieve a catalog snapshot sourced from `shopify_resource_cache` or a future live Shopify sync.

**Files:**

- Create: `backend/app/schemas/catalog.py`
- Create: `backend/app/db/repositories/campaign_catalog.py`
- Create: `backend/app/services/banners/catalog_snapshot_service.py`
- Create: `backend/app/api/v1/catalog.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/unit/test_catalog_snapshot_service.py`
- Test: `backend/tests/api/test_catalog_snapshot.py`

**Endpoints:**

- `POST /api/v1/campaigns/{campaign_id}/catalog-snapshot`
- `GET /api/v1/campaigns/{campaign_id}/catalog-snapshot`

**Verification:**

```bash
cd backend
pytest tests/unit/test_catalog_snapshot_service.py -v
pytest tests/api/test_catalog_snapshot.py -v
pytest -v
```

**Carry-over bugs/gaps:** none. Generation should not proceed without reproducible catalog context when product/SKU claims are used.

---

### Task 8: Implement art direction APIs

**Status:** Completed on 2026-05-30 in branch `feature/backend-mvp-implementation`.

**Completion note:** Added art-direction schemas, Supabase/in-memory repository, service, and `/api/v1/campaigns/{campaign_id}/art-direction` PUT/GET endpoints. The API validates background mode, fold percentage, metadata dictionaries, UUID paths, campaign existence in configured Supabase mode, and one art-direction record per campaign via upsert. Custom model/persona data is persisted as metadata-only per the Task 21 carry-over. Campaign status is intentionally not mutated in Task 8 because the current Supabase status constraint does not include `art_direction_ready`; generation/status transitions remain owned by later generation tasks. Verified with Task 8 tests and full `pytest -q` (`106 passed, 2 skipped`).

**Goal:** Persist art-direction decisions from the frontend Art stage.

**Expected result:** Campaign has a validated art direction record before generation starts.

**Files:**

- Create: `backend/app/schemas/art_direction.py`
- Create: `backend/app/db/repositories/art_directions.py`
- Create: `backend/app/services/banners/art_direction_service.py`
- Create: `backend/app/api/v1/art_direction.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/unit/test_art_direction_service.py`
- Test: `backend/tests/api/test_art_direction.py`

**Endpoints:**

- `PUT /api/v1/campaigns/{campaign_id}/art-direction`
- `GET /api/v1/campaigns/{campaign_id}/art-direction`

**Verification:**

```bash
cd backend
pytest tests/unit/test_art_direction_service.py -v
pytest tests/api/test_art_direction.py -v
pytest -v
```

**Carry-over bugs/gaps:**

- Custom model/persona may be metadata-only.
- Fix/decision point: Task 21; either implement for demo or label as non-MVP.

---

### Task 9: Implement Gemini text client and connect intake skill without breaking deterministic fallback

**Status:** Completed on 2026-05-30 in branch `feature/backend-mvp-implementation`.

**Completion note:** Implemented an import-safe Gemini text client, opt-in `campaign-intake` Gemini provider path via `AIJOLOT_INTAKE_PROVIDER=gemini`, structured Pydantic extraction/JSON fallback, deterministic fallback for tests/dev and provider failures, and synchronous `campaign_store.intake()` wiring that preserves the existing SSE/API contract. Added regression coverage for deterministic default behavior, mocked Gemini success, Gemini-unavailable fallback, stale transcript preservation, noncanonical urgency normalization, empty Gemini strings not erasing current brief fields, and API-level Gemini fallback. Manual live Gemini/ADK credential verification was not run because credentials were not provided. Verified with Task 9 tests and full `pytest -q` (`114 passed, 2 skipped`).

**Goal:** Convert the current deterministic intake seam into a real Gemini/ADK-compatible structured extraction path while keeping deterministic tests stable.

**Expected result:** `campaign-intake` skill can return structured campaign data through Gemini in real mode and deterministic output in tests/fallback mode.

**Files:**

- Modify: `backend/app/agents/tools/gemini_text.py`
- Modify: `backend/app/agents/skills/campaign-intake/impl.py`
- Modify: `backend/app/services/campaign_store.py` or route service layer to use the skill behind a feature flag/provider.
- Modify: `backend/adk_agents/banner_coordinator/agent.py` only if needed.
- Test: `backend/tests/unit/agents/test_campaign_intake_skill.py`
- Test: `backend/tests/api/test_intake.py`

**Existing work to reuse:**

- `backend/app/agents/prompts/intake.md`
- `backend/adk_agents/banner_coordinator/agent.py`
- deterministic `extract_into()` fallback

**Verification:**

```bash
cd backend
pytest tests/unit/agents/test_campaign_intake_skill.py -v
pytest tests/api/test_intake.py -v
pytest -v
```

Manual with credentials:

```bash
cd backend
. .venv/bin/activate
export GOOGLE_API_KEY=<redacted>
adk web --agents_dir adk_agents
```

**Carry-over bugs/gaps:**

- Only intake needs to be truly wired after this task.
- Remaining graph nodes are handled in Tasks 10-14.

---

### Task 10: Implement generation run tracking and 5-step frontend progress facade

**Status:** Completed on 2026-05-30 in branch `feature/backend-mvp-implementation`.

**Completion note:** Added generation run/event schemas, Supabase/in-memory repositories, generation run service, `/api/v1` generation endpoints, and workflow helpers mapping the 12 ADK graph nodes into five frontend progress steps (`intake_context`, `concept`, `image`, `render_audit`, `review_publish`). Task 10 creates deterministic succeeded runs and ordered started/succeeded events for all graph nodes without executing real provider work or mutating campaign status. Supabase-mode compatibility includes explicit event timestamps for deterministic ordering, jsonb summary responses, UUID `started_by` validation, direct run/event campaign-team verification, parent-run same-campaign validation, and stable latest-run tie ordering. Verified with Task 10 tests and full `pytest -q` (`130 passed, 2 skipped`, with two pre-existing Pydantic warnings in `app/agents/state.py`).

**Goal:** Persist generation runs/events and map the scaffolded 12-node graph to frontend-visible progress.

**Expected result:** Frontend can start/poll a generation run and see the 5 visible steps.

**Files:**

- Create: `backend/app/schemas/generation.py`
- Create: `backend/app/db/repositories/generation_runs.py`
- Create: `backend/app/db/repositories/generation_events.py`
- Create: `backend/app/services/banners/generation_run_service.py`
- Create: `backend/app/api/v1/generation.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/workflows/banner_creation.py`
- Test: `backend/tests/unit/test_generation_run_service.py`
- Test: `backend/tests/api/test_generation_runs.py`

**Existing work to reuse:**

- `backend/app/agents/graph.py`
- `backend/app/agents/state.py`
- `backend/app/workflows/banner_creation.py`

**Endpoints:**

- `POST /api/v1/campaigns/{campaign_id}/generation-runs`
- `GET /api/v1/campaigns/{campaign_id}/generation-runs/latest`
- `GET /api/v1/generation-runs/{run_id}`
- `GET /api/v1/generation-runs/{run_id}/events`

**Verification:**

```bash
cd backend
pytest tests/unit/test_generation_run_service.py -v
pytest tests/api/test_generation_runs.py -v
pytest -v
```

**Carry-over bugs/gaps:**

- Generation run can still use stubbed/deterministic node outputs after this task.
- Real node outputs are implemented in Tasks 11-14.

---

### Task 11: Implement brand context, personalization, best-practices/KG, and concept draft skills

**Status:** Completed on 2026-05-30 in branch `feature/backend-mvp-implementation`.

**Completion note:** Implemented deterministic, directly testable ADK skill functions for brand context loading, personalization variants, static best-practices/KG retrieval, concept drafting, and image prompt refinement. Added `kg_documents` repository adapter for the existing KG table with brand-id and vector validation. Brand loading supports Markdown/file fallback by `brand_id`; personalization always includes a default variant and caps total variants at four; KG retrieval is static/no-network and returns no irrelevant padding; concept drafting enforces prohibited words, required phrase preservation, palette token usage, and prompt-safe dynamic fragments; image prompt refinement produces a single 16:9, 60–120 word paragraph with sanitized dynamic inputs and no forbidden text/logo/UI/face-style terms. Verified with Task 11 tests and full `pytest -q` (`137 passed, 2 skipped`, with two pre-existing Pydantic warnings in `app/agents/state.py`).

**Goal:** Fill the first functional half of the scaffolded ADK graph.

**Expected result:** Given campaign + brand + placement + catalog/art context, the workflow can produce a validated `Concept` and personalization variants.

**Files:**

- Modify: `backend/app/agents/skills/brand-context-load/impl.py`
- Modify: `backend/app/agents/skills/user-personalization/impl.py`
- Modify: `backend/app/agents/skills/best-practices-retrieve/impl.py`
- Modify: `backend/app/agents/skills/banner-concept-draft/impl.py`
- Modify: `backend/app/agents/skills/image-prompt-refine/impl.py`
- Modify: `backend/app/agents/tools/kg.py`
- Modify: `backend/app/agents/tools/brand_fs.py` only if still needed for Markdown fallback.
- Create: `backend/app/db/repositories/kg_documents.py` if the existing DB schema includes KG tables; otherwise add an additive migration first.
- Test: `backend/tests/unit/agents/test_context_and_concept_skills.py`

**Do not redo:**

- Do not create a parallel `agents/nodes/load_brand_context.py` unless replacing the skill scaffold intentionally.
- Use existing skill directories as the implementation home.

**Verification:**

```bash
cd backend
pytest tests/unit/agents/test_context_and_concept_skills.py -v
pytest -v
```

**Carry-over bugs/gaps:**

- KG retrieval can start with static docs/deterministic retrieval.
- If embeddings are not ready, Task 21 must either seed embeddings or mark KG as static for demo.

---

### Task 12: Implement image provider, image-generation skill, and usage soft guard

**Status:** Completed on 2026-05-31 in branch `feature/backend-mvp-implementation`.

**Completion note:** Added a typed image provider boundary with deterministic fake PNG provider as the safe default and optional explicit Gemini provider. Updated `nano_banana_image` and `nano-banana-image-generate` to return raw in-memory image bytes plus provider, prompt, usage, and soft-guard metadata for Task 13. Added a generation usage repository adapter and a per-user 15-minute soft guard that warns at the 20th image generation, records in memory for every call, and persists to Supabase only when valid UUID user/team context is available for current schema/RLS. Updated the internal skill contract. Verified with `pytest tests/unit/test_image_provider.py -v`, `pytest tests/unit/test_usage_guard_service.py -v`, and full `pytest -q` (`152 passed, 2 skipped`, with two pre-existing Pydantic warnings in `app/agents/state.py`).

**Goal:** Generate image bytes through a provider boundary and track image usage/cost.

**Expected result:** `nano-banana-image-generate` can call a real or fake provider, and usage warning metadata triggers after 20 image generations per user per 15 minutes.

**Files:**

- Modify: `backend/app/agents/tools/nano_banana_image.py`
- Modify: `backend/app/agents/skills/nano-banana-image-generate/impl.py`
- Create: `backend/app/services/gemini/image_provider.py`
- Create: `backend/app/services/gemini/fake_image_provider.py`
- Create: `backend/app/db/repositories/generation_usage_events.py`
- Create: `backend/app/services/banners/usage_guard_service.py`
- Test: `backend/tests/unit/test_image_provider.py`
- Test: `backend/tests/unit/test_usage_guard_service.py`

**Verification:**

```bash
cd backend
pytest tests/unit/test_image_provider.py -v
pytest tests/unit/test_usage_guard_service.py -v
pytest -v
```

**Carry-over bugs/gaps:**

- Raw image bytes may not yet be optimized/uploaded.
- Fix: Task 13.

---

### Task 13: Implement asset optimization and Supabase Storage upload

**Goal:** Convert raw generated images into responsive durable assets.

**Expected result:** Optimized WebP/AVIF/JPG assets are stored in Supabase Storage and recorded in `banner_assets`.

**Files:**

- Modify: `backend/app/agents/tools/image_optim.py`
- Modify: `backend/app/agents/skills/image-asset-optimize/impl.py`
- Create: `backend/app/services/banners/image_optimizer.py`
- Create: `backend/app/services/banners/asset_service.py`
- Create: `backend/app/db/repositories/banner_assets.py`
- Create: `backend/app/db/repositories/campaign_revisions.py`
- Modify: `backend/app/services/supabase/client.py`
- Test: `backend/tests/unit/test_image_optimizer.py`
- Test: `backend/tests/unit/test_asset_service.py`
- Test: `backend/tests/integration/test_storage_uploads.py`

**Verification:**

```bash
cd backend
pytest tests/unit/test_image_optimizer.py -v
pytest tests/unit/test_asset_service.py -v
pytest -v
```

With Supabase running:

```bash
pytest tests/integration/test_storage_uploads.py -v
```

**Carry-over bugs/gaps:**

- AVIF may be skipped only if the audit report explicitly says `avif_skipped` and the carry-over ledger is updated.
- Fix/decision point: Task 21.

---

### Task 14: Implement HTML/Liquid rendering and audit skills

**Goal:** Produce preview HTML, Shopify Liquid/config payloads, and audit reports.

**Expected result:** The generation workflow can run through audit and stop at human review.

**Files:**

- Modify: `backend/app/agents/tools/html_render.py`
- Modify: `backend/app/agents/tools/liquid_render.py`
- Modify: `backend/app/agents/tools/audit_w3c.py`
- Modify: `backend/app/agents/tools/audit_lighthouse.py`
- Modify: `backend/app/agents/tools/audit_schema.py`
- Modify: `backend/app/agents/tools/audit_log.py`
- Modify: `backend/app/agents/skills/banner-html-seo-render/impl.py`
- Modify: `backend/app/agents/skills/liquid-section-build/impl.py`
- Modify: `backend/app/agents/skills/performance-audit/impl.py`
- Create: `backend/app/services/banners/html_renderer.py`
- Create: `backend/app/services/shopify/liquid_payload_builder.py`
- Create: `backend/app/db/repositories/audit_reports.py`
- Create: `backend/app/db/repositories/audit_events.py`
- Create: `backend/app/api/v1/previews.py`
- Test: `backend/tests/unit/test_html_renderer.py`
- Test: `backend/tests/unit/test_liquid_payload_builder.py`
- Test: `backend/tests/unit/agents/test_audit_skill.py`

**Endpoints:**

- `GET /api/v1/campaigns/{campaign_id}/preview`
- `GET /api/v1/campaigns/{campaign_id}/audit-report`

**Verification:**

```bash
cd backend
pytest tests/unit/test_html_renderer.py -v
pytest tests/unit/test_liquid_payload_builder.py -v
pytest tests/unit/agents/test_audit_skill.py -v
pytest -v
```

**Carry-over bugs/gaps:**

- Full Lighthouse automation may be deferred only if metrics are labeled mock/manual.
- Fix/decision point: Task 21.

---

### Task 15: Implement review canvas comments, refinement requests, and approval workflow

**Goal:** Power the frontend review canvas and all-reviewers approval policy.

**Expected result:** Reviewers can add pinned comments, request changes, resolve comments, and approve. All assigned approvals transition the campaign to `approved`.

**Files:**

- Create: `backend/app/schemas/approvals.py`
- Create: `backend/app/db/repositories/approval_threads.py`
- Create: `backend/app/db/repositories/approval_reviewers.py`
- Create: `backend/app/db/repositories/comments.py`
- Create: `backend/app/db/repositories/refinement_requests.py`
- Create: `backend/app/services/approvals/approval_service.py`
- Create: `backend/app/services/approvals/comment_service.py`
- Create: `backend/app/api/v1/approvals.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/unit/test_approval_service.py`
- Test: `backend/tests/api/test_approvals.py`

**Endpoints:**

- `POST /api/v1/campaigns/{campaign_id}/approval/request`
- `GET /api/v1/campaigns/{campaign_id}/approval`
- `POST /api/v1/approval-threads/{thread_id}/comments`
- `PATCH /api/v1/comments/{comment_id}/resolve`
- `POST /api/v1/approval-threads/{thread_id}/approve`
- `POST /api/v1/approval-threads/{thread_id}/request-changes`
- `POST /api/v1/campaigns/{campaign_id}/refinement-requests`

**Verification:**

```bash
cd backend
pytest tests/unit/test_approval_service.py -v
pytest tests/api/test_approvals.py -v
pytest -v
```

**Carry-over bugs/gaps:**

- Refinement requests may initially be stored without regenerating output.
- Fix: Task 16.

---

### Task 16: Implement regeneration/revision path

**Goal:** Apply requested changes by creating new generation runs/revisions rather than mutating final assets silently.

**Expected result:** A refinement request can trigger regeneration and preserve previous revisions.

**Files:**

- Create: `backend/app/db/repositories/banner_layout_variants.py`
- Create: `backend/app/db/repositories/banner_variants.py`
- Create: `backend/app/services/banners/revision_service.py`
- Modify: `backend/app/workflows/banner_creation.py`
- Modify: `backend/app/api/v1/generation.py`
- Test: `backend/tests/unit/test_revision_service.py`
- Test: `backend/tests/api/test_regeneration.py`

**Endpoints:**

- `POST /api/v1/campaigns/{campaign_id}/variants/{variant_id}/select`
- `POST /api/v1/campaigns/{campaign_id}/regenerate`
- `GET /api/v1/campaigns/{campaign_id}/revisions`

**Verification:**

```bash
cd backend
pytest tests/unit/test_revision_service.py -v
pytest tests/api/test_regeneration.py -v
pytest -v
```

**Carry-over bugs/gaps:**

- If only one layout variant is fully generated, the demo must say so or use deterministic A/B/C variants.
- Fix/decision point: Task 21.

---

### Task 17: Implement scheduling and Shopify publishing

**Goal:** Schedule approved campaigns and publish campaign config to Shopify through a controlled Liquid section.

**Expected result:** Approved campaigns can be scheduled, theme files can be idempotently installed, campaign config can be published/unpublished, and publish jobs are recorded.

**Files:**

- Create: `backend/app/schemas/schedules.py`
- Create: `backend/app/db/repositories/schedules.py`
- Create: `backend/app/db/repositories/scheduled_banners.py`
- Create: `backend/app/db/repositories/publish_jobs.py`
- Create: `backend/app/services/banners/schedule_service.py`
- Modify: `backend/app/agents/skills/schedule-or-publish-route/impl.py`
- Modify: `backend/app/agents/tools/shopify.py`
- Modify: `backend/app/agents/skills/shopify-theme-publish/impl.py`
- Create: `backend/app/services/shopify/client.py`
- Create: `backend/app/services/shopify/theme_files.py`
- Create: `backend/app/services/shopify/metafields.py`
- Create: `backend/app/services/shopify/publisher.py`
- Create: `backend/app/api/v1/schedules.py`
- Create: `backend/app/api/v1/publishing.py`
- Modify: `backend/app/api/v1/router.py`
- Optional migration: `supabase/migrations/<timestamp>_cron_due_publish.sql`
- Test: `backend/tests/unit/test_schedule_service.py`
- Test: `backend/tests/unit/test_shopify_publisher.py`
- Test: `backend/tests/api/test_schedules.py`
- Test: `backend/tests/api/test_publishing.py`

**Endpoints:**

- `POST /api/v1/campaigns/{campaign_id}/schedule`
- `PATCH /api/v1/campaigns/{campaign_id}/schedule`
- `POST /api/v1/campaigns/{campaign_id}/schedule/cancel`
- `POST /api/v1/campaigns/{campaign_id}/publish`
- `POST /api/v1/campaigns/{campaign_id}/unpublish`

**Implementation notes:**

- MVP default: publish active dates in config and let Shopify Liquid show/hide.
- pg_cron due-publish is optional because local `pg_cron`/`pg_net` exist, but do not require cron for demo unless explicitly chosen.
- Search-result placement must either publish correctly or return a clear unsupported error.

**Verification:**

```bash
cd backend
pytest tests/unit/test_schedule_service.py -v
pytest tests/unit/test_shopify_publisher.py -v
pytest tests/api/test_schedules.py -v
pytest tests/api/test_publishing.py -v
pytest -v
```

Manual with Shopify credentials:

- Install/update Liquid files.
- Publish approved scheduled campaign.
- Verify target Shopify page displays the banner.
- Unpublish and verify rollback.

**Carry-over bugs/gaps:**

- No active pg_cron job is acceptable if theme-enforced dates are used.
- If demo requires automatic due-publish, cron must be implemented here.

---

### Task 18: Integrate current static frontend with backend APIs

**Goal:** Connect the existing prototype to real backend endpoints without doing the full Next.js migration.

**Expected result:** The static frontend can exercise the demo flow against FastAPI.

**Files:**

- Modify: `frontend/lib.jsx`
- Modify: `frontend/data.jsx` only where API-backed adapters replace static data.
- Modify relevant frontend stage files only when necessary for API wiring.
- Create: `docs/architecture/frontend-backend-contract.md`
- Test/manual: browser flow.

**Implementation notes:**

- Use `window.AIJOLOT_API_BASE` defaulting to `http://localhost:8000`.
- Preserve mock fallback only if visibly labeled.
- Prefer `/api/v1` routes for new code.
- Root compatibility routes can remain only while needed by the prototype.

**Verification:**

Terminal 1:

```bash
cd backend
. .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```bash
python3 -m http.server 5500 --directory frontend
```

Manual:

- Brand loads/saves.
- Campaign intake works.
- Placement saves.
- Art direction saves.
- Generation progress displays.
- Review/approval works.
- Schedule/publish controls respect backend status.

**Carry-over bugs/gaps:**

- Full Next.js migration remains frontend-owned.
- Static adapters should be removed during migration, not by backend MVP work.

---

### Task 19: Auth/team context and RLS alignment

**Goal:** Add enough user/team scoping for MVP without exposing service role secrets.

**Expected result:** Backend can associate records to a user/team and enforce no cross-team leakage through API responses.

**Files:**

- Create: `backend/app/core/auth.py`
- Create: `backend/app/services/auth/user_context.py`
- Modify: `backend/app/api/v1/*.py`
- Optional migration: `supabase/migrations/<timestamp>_rls_policy_refinement.sql`
- Test: `backend/tests/unit/test_auth_context.py`
- Test: `backend/tests/api/test_auth_boundaries.py`

**Verification:**

```bash
cd backend
pytest tests/unit/test_auth_context.py -v
pytest tests/api/test_auth_boundaries.py -v
pytest -v
cd ..
supabase db reset
```

**Carry-over bugs/gaps:**

- Fully polished login UX is frontend-owned.
- No backend leakage of service role keys or cross-team data is allowed.

---

### Task 20: Performance/evolutionary memory API

**Goal:** Power the prototype's performance screen with schema-backed mock/manual metrics.

**Expected result:** Performance snapshots, optimization insights, and proposed V2 campaigns can be displayed without claiming live analytics.

**Files:**

- Create: `backend/app/schemas/performance.py`
- Create: `backend/app/db/repositories/performance_snapshots.py`
- Create: `backend/app/db/repositories/optimization_insights.py`
- Create: `backend/app/db/repositories/optimization_proposals.py`
- Create: `backend/app/services/banners/performance_service.py`
- Create: `backend/app/api/v1/performance.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/unit/test_performance_service.py`
- Test: `backend/tests/api/test_performance.py`

**Verification:**

```bash
cd backend
pytest tests/unit/test_performance_service.py -v
pytest tests/api/test_performance.py -v
pytest -v
```

**Carry-over bugs/gaps:**

- Live Shopify/analytics ingestion is non-MVP unless the team changes scope.

---

### Task 21: Demo hardening and carry-over gap closure

**Goal:** Remove or explicitly constrain every gap that could break the hackathon demo.

**Expected result:** The chosen demo path can run twice after reset with real providers or deterministic fallback.

**Files:**

- Create: `docs/demo-script.md`
- Create: `demo/scenarios/avocado-black-friday.md`
- Create: `demo/scenarios/onboarding-scheduled.md`
- Create: `demo/scenarios/apparel-vip-product-launch.md`
- Create: `scripts/reset-demo-data.sh` or `scripts/reset-demo-data.py`
- Create: `scripts/smoke-demo-flow.py`
- Modify: `supabase/seed.sql` if needed.
- Modify: this plan if any gap changes.

**Must decide/fix here:**

- PDF/Figma/brandbook import: real extraction or clearly labeled partial/mock.
- Live Shopify resource sync: real sync or demo locked to seeded resources.
- Custom model/persona: real support or explicitly non-MVP.
- AVIF: enabled or audit-labeled skipped.
- Lighthouse: real automation or labeled mock/manual metrics.
- A/B/C layout variants: real generated variants or deterministic/demo-labeled variants.
- KG retrieval: embeddings or static deterministic retrieval.

**Verification:**

```bash
supabase db reset
cd backend
pytest -v
cd ..
python3 scripts/smoke-demo-flow.py
```

Manual:

- Run complete demo flow twice.
- Verify Shopify publish/unpublish if credentials are available.

**Carry-over bugs/gaps:** none allowed for the chosen demo path.

---

### Task 22: Documentation cleanup and handoff

**Goal:** Keep docs accurate after implementation.

**Expected result:** README, API docs, frontend contract, and this plan match real behavior.

**Files:**

- Modify: `README.md`
- Modify: `docs/architecture/api-contract.md`
- Modify: `docs/architecture/frontend-backend-contract.md`
- Modify: `docs/architecture/project-structure.md`
- Modify: `docs/plans/2026-05-28-banner-creator-mvp.md`

**Verification:**

```bash
git status --short
cd backend
pytest -v
cd ..
supabase db reset
```

Manual:

- Follow README from fresh setup.
- Open backend API docs.
- Open static frontend.
- Complete documented demo path.

**Carry-over bugs/gaps:** none in docs. If a feature is incomplete, docs must say so.

---

## 6. API Surface Summary

Canonical target API base:

```text
/api/v1
```

Temporary root-level routes currently exist and must be preserved until frontend integration no longer needs them:

- `GET /brands`
- `GET /brands/{brand_id}`
- `PUT /brands/{brand_id}`
- `POST /campaigns/intake`
- `GET /campaigns/{campaign_id}`
- `PATCH /campaigns/{campaign_id}`

New implementation should prefer `/api/v1`.

Planned canonical endpoints:

- `GET /health`
- `GET /api/v1/brands`
- `GET /api/v1/brands/{brand_id}`
- `PUT /api/v1/brands/{brand_id}`
- `POST /api/v1/brands/import`
- `GET /api/v1/stores`
- `GET /api/v1/stores/{store_id}`
- `GET /api/v1/stores/{store_id}/shopify/resources`
- `GET /api/v1/stores/{store_id}/placement-types`
- `GET /api/v1/stores/{store_id}/placement-types/{placement_type_key}/targets`
- `POST /api/v1/placements/validate`
- `POST /api/v1/campaigns`
- `GET /api/v1/campaigns`
- `GET /api/v1/campaigns/{campaign_id}`
- `PATCH /api/v1/campaigns/{campaign_id}`
- `POST /api/v1/campaigns/intake`
- `POST /api/v1/campaigns/{campaign_id}/placement`
- `GET /api/v1/campaigns/{campaign_id}/placement`
- `POST /api/v1/campaigns/{campaign_id}/catalog-snapshot`
- `GET /api/v1/campaigns/{campaign_id}/catalog-snapshot`
- `PUT /api/v1/campaigns/{campaign_id}/art-direction`
- `GET /api/v1/campaigns/{campaign_id}/art-direction`
- `POST /api/v1/campaigns/{campaign_id}/generation-runs`
- `GET /api/v1/campaigns/{campaign_id}/generation-runs/latest`
- `GET /api/v1/generation-runs/{run_id}`
- `GET /api/v1/generation-runs/{run_id}/events`
- `GET /api/v1/campaigns/{campaign_id}/preview`
- `GET /api/v1/campaigns/{campaign_id}/audit-report`
- `POST /api/v1/campaigns/{campaign_id}/approval/request`
- `GET /api/v1/campaigns/{campaign_id}/approval`
- `POST /api/v1/approval-threads/{thread_id}/comments`
- `PATCH /api/v1/comments/{comment_id}/resolve`
- `POST /api/v1/approval-threads/{thread_id}/approve`
- `POST /api/v1/approval-threads/{thread_id}/request-changes`
- `POST /api/v1/campaigns/{campaign_id}/refinement-requests`
- `POST /api/v1/campaigns/{campaign_id}/regenerate`
- `GET /api/v1/campaigns/{campaign_id}/revisions`
- `POST /api/v1/campaigns/{campaign_id}/schedule`
- `PATCH /api/v1/campaigns/{campaign_id}/schedule`
- `POST /api/v1/campaigns/{campaign_id}/schedule/cancel`
- `POST /api/v1/campaigns/{campaign_id}/publish`
- `POST /api/v1/campaigns/{campaign_id}/unpublish`
- `GET /api/v1/campaigns/{campaign_id}/performance`
- `POST /api/v1/campaigns/{campaign_id}/performance/snapshots`
- `POST /api/v1/campaigns/{campaign_id}/optimization-proposals`

---

## 7. Verification Gates

### Per task

```bash
cd backend
. .venv/bin/activate
pytest -v
```

If a task touches Supabase schema/seed:

```bash
cd ..
supabase db reset
```

If a task touches frontend integration:

```bash
python3 -m http.server 5500 --directory frontend
```

### Before demo

```bash
supabase db reset
cd backend
. .venv/bin/activate
pytest -v
cd ..
python3 scripts/smoke-demo-flow.py
```

Manual demo checklist:

- Backend starts.
- Static frontend opens.
- Brand context loads.
- Campaign intake works.
- Campaign persists across backend restart.
- Placement saves.
- Catalog snapshot saves.
- Art direction saves.
- Generation run reaches audit/HITL.
- Preview loads.
- Pinned comments work.
- All-reviewer approval unlocks scheduling.
- Schedule saves.
- Publish succeeds or deterministic fallback is explicitly labeled.
- Shopify storefront shows banner in selected placement if credentials are available.
- Unpublish/rollback works if publishing is demonstrated.

---

## 8. Carry-Over Bug/Gaps Ledger

No temporary gap is allowed unless it is listed here with an owner task.

| Gap | Allowed after task | Must be fixed/decided in | Notes |
| --- | --- | --- | --- |
| Current tests cannot run in active shell because pytest is not installed | Current main | Task 0 | Environment/setup gap, not known code failure. |
| Brand endpoints are Markdown/file-backed | Current main / Task 1 | Task 3 | Runtime source of truth must become Supabase. |
| Campaign/intake store is in-memory | Current main / Task 3 | Task 4 | Must persist to Supabase before relying on it. |
| Root-level routes only; no canonical `/api/v1` yet | Current main | Task 2 | Preserve compatibility while adding v1. |
| Intake is deterministic/rule-based, not Gemini-backed | Current main / Task 4 | Task 9 | Keep deterministic fallback for tests. |
| ADK graph, coordinator, tools, and skills are scaffolded but mostly `NotImplementedError` | Current main | Tasks 9-17 | Each task owns specific skill/tool replacement. |
| `run_to_audit()` and `resume_after_hitl()` are not implemented | Current main / Task 10 | Tasks 14 and 17 | `run_to_audit` after render/audit; resume after schedule/publish. |
| Brand write/import endpoints are unauthenticated | Task 3 | Task 19 | Local/dev MVP can proceed, but deployed backend must protect service-role-backed writes. |
| Live Shopify resource sync missing | Task 5 | Task 17 or Task 21 | Seeded cache is enough only if demo uses seeded resources. |
| Search-result placement validates but may not publish | Task 6 | Task 17 | Either implement or block with clear unsupported error. |
| Custom model/persona is metadata-only | Task 8 | Task 21 or explicitly non-MVP | Do not imply real custom model generation exists. |
| Raw image bytes not optimized/stored | Task 12 | Task 13 | No review/publish with raw temp assets. |
| AVIF omitted or flaky | Task 13 | Task 21 | Either enable or mark skipped in audit. |
| Lighthouse automation placeholder | Task 14 | Task 21 | Metrics must be honest: real, seeded, or mock/manual. |
| Refinement requests stored but not applied | Task 15 | Task 16 | Comments must not silently mutate final asset. |
| No active pg_cron due-publish job | Task 17 | Task 17 only if demo requires auto due-publish | Theme-enforced dates are MVP default. |
| Static frontend API adapters exist | Task 18 | Frontend migration, outside backend MVP | Not a backend bug if documented. |

---

## 9. Immediate Next Steps

1. Run Task 0 to install backend dev dependencies and verify current merged tests.
2. Run Task 1 to add settings/dependency boundaries.
3. Run Task 2 to add `/api/v1` without breaking current root routes.
4. Run Tasks 3-4 to move brand and campaign runtime storage to Supabase.
5. Continue through Tasks 5-8 to complete non-agentic campaign setup APIs.
6. Use existing ADK scaffold for Tasks 9-14; do not create a parallel graph.
7. Implement review/schedule/publish in Tasks 15-17.
8. Integrate the current static frontend in Task 18.
9. Close demo gaps in Task 21 before rehearsing.
