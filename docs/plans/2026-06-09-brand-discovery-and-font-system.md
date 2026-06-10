# Brand Discovery and Font System Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task. This plan extends the current brand color role work; do not start implementation until `feature/brand-color-roles-ai-palettes` is either committed/merged or explicitly chosen as the base branch.

**Goal:** Add an agent-driven brand discovery flow that imports brand signals from Shopify, recommends editable brand color palettes, and adds an approved/discarded font family system that generation can use safely.

**Architecture:** Add a new Brand Discovery layer before or alongside Brand Context editing. Shopify-derived raw evidence is stored separately from approved brand settings. Gemini turns discovered evidence into recommendations, but the user remains the approval gate: colors and fonts become active only after being accepted into `BrandContext.color_system` or the new typography/font system. Keep root prototype routes where useful, but canonical integration must use `/api/v1` with request-scoped team/store context.

**Tech Stack:** FastAPI, Pydantic v2, Supabase/Postgres JSONB, Shopify Admin GraphQL/REST theme assets, Gemini text/vision where available, static React UMD/Babel frontend, current BrandContext color_system and palette suggestions services.

---

## Current Repository Reality

Verified on 2026-06-09:

- Repo: `/Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent`
- Active branch: `feature/brand-color-roles-ai-palettes`
- Worktree contains the uncommitted brand color role + Gemini palette suggestion implementation.
- Current brand model source: `backend/app/schemas/brand.py`
- Current color role architecture doc: `docs/architecture/brand-context-color-system.md`
- Current palette suggestion service/routes:
  - `backend/app/services/brands/palette_suggestions.py`
  - `backend/app/api/brands.py`
  - `backend/app/api/v1/brands.py`
- Current Shopify client has Admin REST and GraphQL support in `backend/app/services/shopify/client.py`.
- Current Shopify resource/cache services do not perform live brand/theme discovery; `backend/app/services/shopify/resource_service.py` intentionally reads Supabase cache or seeds only.
- Current BrandContext has `typography.display` and `typography.body` as simple strings only. It does not yet model font candidates, approved/discarded fonts, font roles, or source evidence.
- Current frontend Brand Context editor already edits role-based colors and draft AI palette suggestions in `frontend/BrandContextView.jsx`.

## Product Direction

There are two big features:

1. Brand Discovery at the beginning
   - User connects or selects a Shopify store.
   - Agent pulls Shopify brand evidence: shop name, logo, brand colors if available, theme settings, active theme assets, homepage/hero/banner imagery, existing banner sections, and relevant style/font references.
   - Agent summarizes discovered evidence and recommends a BrandContext draft.
   - User can accept/tweak/save color roles, variants, logo, image directives, and typography settings.

2. Font Discovery and Approval System
   - Agent discovers existing font families from Shopify theme settings/assets and storefront CSS when available.
   - Agent recommends a wide set of compatible font families.
   - User can approve fonts, discard fonts, and assign approved fonts to roles such as display/headline/body/accent.
   - Generation and Liquid output must use only approved font families, with safe fallbacks.

## Key Design Principles

- Discovery evidence is not the same as approved brand context.
- Never overwrite approved user settings silently from Shopify discovery.
- Gemini recommendations are suggestions; user acceptance makes them active.
- Store raw discovery evidence with source/provenance so later audits can explain recommendations.
- Existing `palette` and `color_system` must remain backward compatible.
- Existing `typography.display` and `typography.body` must remain backward compatible.
- `/api/v1` routes must require request context and use request-scoped team/store services.
- Root prototype routes can exist for local demo compatibility, but new frontend integration should prefer `/api/v1`.
- Do not log or store Shopify access tokens, Gemini keys, or raw secrets.
- Brand discovery may use deterministic extraction/parsing for Shopify evidence, but AI recommendations should be clearly labeled as Gemini-backed when using AI.

---

## Proposed Data Contracts

### BrandDiscoverySnapshot

Create a snapshot object that stores discovered evidence before user approval.

Suggested schema:

```python
class BrandDiscoveryAsset(BaseModel):
    kind: Literal["logo", "banner", "hero", "theme_asset", "css", "settings", "unknown"]
    url: str | None = None
    shopify_gid: str | None = None
    theme_asset_key: str | None = None
    content_type: str | None = None
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)

class DiscoveredColor(BaseModel):
    hex: str
    name: str = ""
    source: str
    confidence: float = Field(default=0.0, ge=0, le=1)
    usage_hint: str = ""

class DiscoveredFont(BaseModel):
    family: str
    source: str
    css_stack: str = ""
    confidence: float = Field(default=0.0, ge=0, le=1)
    sample_usage: str = ""

class BrandDiscoverySnapshot(BaseModel):
    id: str
    brand_id: str
    store_id: str | None = None
    shop_domain: str
    status: Literal["pending", "running", "succeeded", "failed", "partial"]
    discovered_at: datetime
    source_summary: str = ""
    assets: list[BrandDiscoveryAsset] = Field(default_factory=list)
    colors: list[DiscoveredColor] = Field(default_factory=list)
    fonts: list[DiscoveredFont] = Field(default_factory=list)
    theme_metadata: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
```

### BrandRecommendationDraft

Create a recommendation draft generated from discovery evidence.

```python
class BrandColorRecommendation(BaseModel):
    role_key: Literal["primary", "secondary", "tertiary"]
    base_hex: str
    label: str
    usage_hint: str
    agent_hint: str
    variants: list[BrandColorVariant] = Field(default_factory=list)
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)

class FontCandidate(BaseModel):
    family: str
    css_stack: str
    category: Literal["sans", "serif", "display", "mono", "handwritten", "unknown"] = "unknown"
    source: Literal["shopify_theme", "storefront_css", "gemini_suggested", "system_seed", "manual"]
    status: Literal["candidate", "approved", "discarded"] = "candidate"
    recommended_roles: list[Literal["display", "headline", "body", "accent", "caption"]] = Field(default_factory=list)
    rationale: str = ""
    evidence_refs: list[str] = Field(default_factory=list)

class BrandTypographySystem(BaseModel):
    display: str = "Space Grotesk"  # legacy compatible
    body: str = "Inter"             # legacy compatible
    headline: str | None = None
    accent: str | None = None
    approved_fonts: list[FontCandidate] = Field(default_factory=list)
    discarded_fonts: list[FontCandidate] = Field(default_factory=list)
```

Backward compatibility:

- Keep `BrandContext.typography.display` and `BrandContext.typography.body` working.
- Add optional `typography_system` or evolve `Typography` carefully. Preferred: extend `Typography` with optional fields while keeping `display` and `body` required/defaulted.
- HTML and Liquid should resolve fonts from approved fonts first, then legacy display/body strings.

### Supabase Storage

Add first-class JSONB columns rather than burying durable data in metadata:

```sql
alter table public.brand_contexts
  add column if not exists discovery_snapshot jsonb,
  add column if not exists typography_system jsonb;

create index if not exists brand_contexts_discovery_snapshot_gin_idx
  on public.brand_contexts using gin (discovery_snapshot);

create index if not exists brand_contexts_typography_system_gin_idx
  on public.brand_contexts using gin (typography_system);
```

If the discovery history should be retained over time, add a separate table instead of only storing the latest snapshot:

```sql
create table if not exists public.brand_discovery_runs (
  id uuid primary key default gen_random_uuid(),
  team_id text not null,
  store_id text,
  brand_id text not null,
  status text not null,
  snapshot jsonb not null default '{}'::jsonb,
  recommendation jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

Recommendation: use both:

- `brand_discovery_runs` for history/debuggability.
- Latest accepted/applied fields on `brand_contexts` for active generation.

---

## Shopify Discovery Sources

Priority order:

1. Shop metadata
   - `shop { name primaryDomain { url host } brand { ... } }` if available in the Admin API version/scopes.
   - Use as low-risk metadata.

2. Active theme metadata
   - Active/main theme id/name.
   - Theme settings and relevant assets.
   - `config/settings_data.json` for current theme colors/fonts/logo references.
   - `config/settings_schema.json` for theme setting definitions.

3. Theme assets
   - CSS/theme files: `assets/*.css`, `assets/*.scss.liquid`, `assets/*.css.liquid`.
   - Layout/templates/sections likely to contain hero/banner/logo references.
   - Do not pull every large asset blindly. Use allowlists, byte caps, and key filters.

4. Storefront pages/images
   - Existing resource cache for products/collections may contribute image URLs.
   - Homepage/hero/banner references can be extracted from theme settings and sections.
   - Optional later: safe public storefront HTML fetch for CSS/font references if CORS/robots and demo constraints allow.

5. Existing BrandContext
   - Existing user-approved settings must be part of the prompt so recommendations improve rather than overwrite.

---

## API Plan

Canonical `/api/v1` routes:

```text
POST /api/v1/brands/{brand_id}/discovery-runs
GET  /api/v1/brands/{brand_id}/discovery-runs/{run_id}
POST /api/v1/brands/{brand_id}/discovery-runs/{run_id}/recommendations
POST /api/v1/brands/{brand_id}/apply-discovery-recommendations
POST /api/v1/brands/{brand_id}/font-suggestions
```

Prototype/root compatibility routes can mirror these later if the static frontend needs them:

```text
POST /brands/{brand_id}/discovery-runs
GET  /brands/{brand_id}/discovery-runs/{run_id}
POST /brands/{brand_id}/apply-discovery-recommendations
POST /brands/{brand_id}/font-suggestions
```

Request/response behavior:

- Starting discovery returns a run object with status and snapshot/recommendation when complete.
- The first implementation can be synchronous with clear timeout/caps if the live Shopify calls are small.
- Later implementation can move to background job/SSE events if discovery becomes slow.
- Applying recommendations requires an explicit request body that lists accepted color roles, variants, fonts, logo, and directives.
- Font suggestions must not auto-approve. They return candidates.

---

## Implementation Tasks

### Task 0: Branch and plan alignment

**Objective:** Start from a safe base after the current color-role feature is committed or explicitly selected as the base.

**Files:**
- No source changes expected.

**Steps:**
1. Verify current feature status:
   ```bash
   cd /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent
   git status --short --branch
   ```
2. If `feature/brand-color-roles-ai-palettes` is not committed, stop and either commit it or ask Pk whether to branch from it.
3. Create a focused branch:
   ```bash
   git checkout -b feature/shopify-brand-discovery-font-system
   ```

**Acceptance:** Work starts from a known branch with the brand color role implementation available.

### Task 1: Add discovery and typography schema tests

**Objective:** Define backend data contracts before implementation.

**Files:**
- Modify: `backend/app/schemas/brand.py`
- Create: `backend/app/schemas/brand_discovery.py`
- Create: `backend/tests/unit/test_brand_discovery_schema.py`
- Modify: `backend/tests/unit/test_brand_color_system.py`

**Tests:**
- Existing BrandContext payloads still validate.
- `Typography` still supports legacy `{display, body}` only.
- New typography system supports approved/discarded/candidate fonts.
- Font family values reject script/CSS injection characters.
- Discovery snapshot stores assets/colors/fonts with source/confidence.
- Recommendation draft can be applied without losing existing color_system.

**Validation:**
```bash
cd backend
. .venv/bin/activate
pytest tests/unit/test_brand_discovery_schema.py -v tests/unit/test_brand_color_system.py -v
```

### Task 2: Add Supabase persistence for discovery and fonts

**Objective:** Persist latest discovery snapshot and typography system with compatibility for existing brand records.

**Files:**
- Create: `supabase/migrations/YYYYMMDDHHMMSS_add_brand_discovery_and_typography.sql`
- Modify: `backend/app/db/repositories/brand_contexts.py`
- Modify: `backend/app/services/brands/brand_service.py`
- Modify: `backend/tests/integration/test_brand_context_repository.py`
- Modify: `backend/tests/api/test_brands.py`

**Implementation:**
- Add `discovery_snapshot jsonb` and `typography_system jsonb` to `brand_contexts`.
- Repository should include these top-level columns in upsert/get/list paths.
- Brand service should read top-level fields first, with optional legacy metadata fallback only if needed.

**Validation:**
```bash
supabase db reset
cd backend
. .venv/bin/activate
pytest tests/integration/test_brand_context_repository.py -v tests/api/test_brands.py -v
```

### Task 3: Shopify theme/brand evidence collector

**Objective:** Pull safe brand evidence from Shopify using existing Admin client patterns.

**Files:**
- Modify: `backend/app/services/shopify/client.py`
- Modify: `backend/app/services/shopify/graphql_queries.py`
- Create: `backend/app/services/brands/shopify_discovery.py`
- Create: `backend/tests/unit/test_shopify_brand_discovery.py`

**Implementation:**
- Add Shopify client methods for:
  - shop metadata GraphQL query
  - theme list/main theme lookup
  - theme asset GET for selected keys
- Pull only allowlisted/capped assets:
  - `config/settings_data.json`
  - `config/settings_schema.json`
  - CSS assets under a byte cap
  - section/template files likely to contain banner/hero/logo references under a byte cap
- Extract:
  - logo references
  - hex colors
  - CSS variables with color-like values
  - font-family declarations
  - theme setting IDs/names related to color/font/logo/banner
  - banner/hero image URLs or theme asset references
- Store every extracted item with source reference.

**Safety:**
- Never log access tokens.
- Do not fetch arbitrary external URLs in the first version.
- If Shopify scopes are missing, return partial discovery with errors, not a crash.

**Validation:**
```bash
cd backend
. .venv/bin/activate
pytest tests/unit/test_shopify_brand_discovery.py -v
```

### Task 4: Discovery run service and API routes

**Objective:** Expose discovery as an explicit backend workflow.

**Files:**
- Create: `backend/app/services/brands/brand_discovery_service.py`
- Modify: `backend/app/api/brands.py`
- Modify: `backend/app/api/v1/brands.py`
- Create/modify: `backend/tests/api/test_brand_discovery.py`

**Implementation:**
- Root route may use configured/default demo service.
- `/api/v1` route must require request context and use request team/store scope.
- `POST /api/v1/brands/{brand_id}/discovery-runs` should:
  - verify brand belongs to request team
  - verify store context if store_id is provided
  - run collector with caps
  - persist discovery run/snapshot
  - return status `succeeded`, `partial`, or `failed`
- Include clear `503` for unavailable Shopify config/client.

**Validation:**
```bash
cd backend
. .venv/bin/activate
pytest tests/api/test_brand_discovery.py -v tests/api/test_auth_boundaries.py -v
```

### Task 5: Gemini recommendation service for discovered colors

**Objective:** Convert Shopify evidence into recommended brand color roles and variants.

**Files:**
- Modify: `backend/app/services/brands/palette_suggestions.py` or create `backend/app/services/brands/brand_recommendations.py`
- Create: `backend/tests/unit/test_brand_recommendations.py`
- Modify: `backend/tests/api/test_brand_discovery.py`

**Implementation:**
- Prompt Gemini with:
  - discovered colors and sources
  - logo/banner/theme evidence summary
  - existing approved brand context
  - current role semantics
- Return recommended `primary`, `secondary`, `tertiary`, variants, rationale, evidence refs.
- Validate/dedupe hex colors.
- Do not auto-save into active BrandContext.
- If Gemini is unavailable, return clear `503`; do not fake AI recommendations.

**Validation:**
```bash
cd backend
. .venv/bin/activate
pytest tests/unit/test_brand_recommendations.py -v tests/api/test_brand_discovery.py -v
```

### Task 6: Font candidate extraction and recommendation service

**Objective:** Add a first-class font recommendation workflow.

**Files:**
- Create: `backend/app/services/brands/font_discovery.py`
- Create: `backend/app/services/brands/font_suggestions.py`
- Create: `backend/tests/unit/test_font_discovery.py`
- Create: `backend/tests/unit/test_font_suggestions.py`

**Implementation:**
- Deterministically extract font-family declarations from theme settings/CSS evidence.
- Normalize font family names and CSS stacks.
- Reject unsafe CSS/font input.
- Add a curated seed list for safe fallback candidates, clearly labeled `system_seed`.
- Gemini may recommend combinations from discovered fonts plus safe seed families:
  - display/headline/body/accent/caption roles
  - rationale
  - category
  - compatibility notes
- User-facing AI font suggestions should be Gemini-backed when called AI; deterministic seed fonts are allowed only as non-AI fallback candidates explicitly labeled as such.

**Validation:**
```bash
cd backend
. .venv/bin/activate
pytest tests/unit/test_font_discovery.py -v tests/unit/test_font_suggestions.py -v
```

### Task 7: Apply accepted discovery recommendations

**Objective:** Let the user explicitly apply accepted colors/fonts/logo/directives into BrandContext.

**Files:**
- Create: `backend/app/schemas/brand_recommendations.py`
- Modify: `backend/app/services/brands/brand_service.py`
- Modify: `backend/app/api/brands.py`
- Modify: `backend/app/api/v1/brands.py`
- Create/modify: `backend/tests/api/test_brand_discovery.py`

**Implementation:**
- Request body lists accepted items:
  - accepted color roles/variants
  - accepted logo URL/reference
  - accepted image directives
  - approved font candidates
  - discarded font candidates
  - assigned typography roles
- Save only accepted values into active BrandContext.
- Preserve existing values when a recommendation is not accepted.
- Keep legacy `palette`, `typography.display`, and `typography.body` synchronized for old generation paths.

**Validation:**
```bash
cd backend
. .venv/bin/activate
pytest tests/api/test_brand_discovery.py -v tests/unit/test_brand_color_system.py -v
```

### Task 8: Generation integration for approved fonts

**Objective:** Make banner creation use approved fonts safely.

**Files:**
- Modify: `backend/app/agents/skills/banner-concept-draft/impl.py`
- Modify: `backend/app/agents/skills/image-prompt-refine/impl.py`
- Modify: `backend/app/services/banners/html_renderer.py`
- Modify: `backend/app/services/shopify/liquid_payload_builder.py`
- Modify: `backend/tests/unit/agents/test_context_and_concept_skills.py`
- Modify: `backend/tests/unit/test_html_renderer.py`
- Modify: `backend/tests/unit/test_liquid_payload_builder.py`

**Implementation:**
- Concept/image prompt should include approved typography role guidance.
- HTML renderer should use approved display/body font stacks, with safe fallback.
- Liquid payload should include typography system/config and safe CSS variables/settings.
- If no approved fonts exist, keep legacy `typography.display` and `typography.body` behavior.

**Validation:**
```bash
cd backend
. .venv/bin/activate
pytest tests/unit/agents/test_context_and_concept_skills.py -v tests/unit/test_html_renderer.py -v tests/unit/test_liquid_payload_builder.py -v
```

### Task 9: Frontend Discovery Review UI

**Objective:** Add a user-friendly beginning flow to discover, review, tweak, approve, and save brand settings.

**Files:**
- Modify: `frontend/BrandContextView.jsx`
- Modify: `frontend/data.jsx`
- Optional create: `frontend/BrandDiscoveryView.jsx`

**UI requirements:**
- Add a `Brand Discovery` entry point before or at the top of Brand Context.
- Show discovery states:
  - not started
  - running
  - partial with warnings
  - succeeded
  - failed
- Show discovered evidence grouped by source:
  - logo/assets
  - colors
  - fonts
  - banners/hero images
  - theme settings
- Show recommended color roles/variants with rationale and accept controls.
- Show font candidates grouped by status:
  - recommended/candidate
  - approved
  - discarded
- User can approve/discard fonts and assign approved fonts to display/headline/body/accent roles.
- Nothing becomes active until Save/Apply is clicked.
- Offline fallback must clearly say discovery requires backend/Shopify and cannot be faked.

**Validation:**
```bash
node --check frontend/data.jsx
npx esbuild frontend/BrandContextView.jsx --bundle --outfile=/tmp/brandcontext-discovery-check.js --format=iife --log-level=error
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5500/
```

### Task 10: Documentation and frontend handoff

**Objective:** Document the new discovery/font contracts and how frontend should call them.

**Files:**
- Create: `docs/architecture/brand-discovery-and-font-system.md`
- Modify: `docs/architecture/api-contract.md`
- Modify: `docs/architecture/frontend-integration-function-reference.md`
- Modify: `docs/architecture/brand-context-color-system.md`

**Document:**
- Discovery snapshot and recommendation contracts.
- Shopify evidence sources and safety caps.
- AI/Gemini behavior and unavailable states.
- Apply/approval semantics.
- Font candidate lifecycle: candidate, approved, discarded.
- Generation usage rules for approved fonts.
- Known gaps and future enhancements.

**Validation:**
```bash
git diff --check docs/architecture docs/plans
```

### Task 11: Final integration verification

**Objective:** Prove both features are ready for demo/testing.

**Commands:**
```bash
supabase db reset
cd backend
. .venv/bin/activate
pytest tests/unit/test_brand_discovery_schema.py -v
pytest tests/unit/test_shopify_brand_discovery.py -v
pytest tests/unit/test_brand_recommendations.py -v
pytest tests/unit/test_font_discovery.py -v
pytest tests/unit/test_font_suggestions.py -v
pytest tests/api/test_brand_discovery.py -v
pytest tests/unit/agents/test_context_and_concept_skills.py -v tests/unit/test_html_renderer.py -v tests/unit/test_liquid_payload_builder.py -v
pytest -q
cd ..
git diff --check
npx esbuild frontend/BrandContextView.jsx --bundle --outfile=/tmp/brandcontext-discovery-final-check.js --format=iife --log-level=error
```

**Manual/live smoke when credentials are available:**
- Start backend with Shopify/Gemini env.
- Start discovery for a connected demo store.
- Confirm discovery snapshot includes at least one evidence source or a clear partial warning.
- Confirm recommendations are Gemini-backed.
- Accept one color variant and one font candidate.
- Save/apply.
- Generate a banner and confirm color/font settings are present in HTML/Liquid config.

---

## Acceptance Criteria

Brand Discovery:

- Agent can start from Shopify/store evidence before user manually edits Brand Context.
- Discovery pulls or partially pulls logo/theme/color/font/banner evidence with source metadata.
- Missing Shopify scopes/config return clear partial/503 states, not silent fake discovery.
- Recommendations are shown as drafts and do not overwrite approved settings automatically.
- User can accept/tweak/save recommendations into BrandContext.

Color Recommendations:

- Recommended palettes integrate with existing `color_system` roles and variants.
- Gemini-backed recommendations include rationale and evidence references.
- Existing per-role AI Palette Suggestions remain available after discovery.
- Legacy palette compatibility remains intact.

Font System:

- Discovered and suggested fonts are represented as candidates.
- User can approve and discard fonts.
- Approved fonts can be assigned to display/headline/body/accent/body roles.
- Generation uses approved fonts only, with safe fallback to legacy typography fields.
- Liquid/HTML outputs sanitize font family values and do not allow CSS injection.

Frontend:

- Brand editor includes discovery start/review/apply flow.
- Color and font recommendations are draft-only until Save/Apply.
- Offline fallback remains explicit and does not fake Shopify or AI discovery.

Security/Boundaries:

- No token/secret logging.
- `/api/v1` routes require request context and team/store scoping.
- Shopify discovery uses caps/allowlists and handles missing scopes gracefully.
- Full tests and frontend static checks pass.

---

## Known Carry-Over Gaps / Later Enhancements

- True async/background discovery jobs with progress streaming.
- Screenshot/visual extraction from live storefront pages.
- Image-based color extraction from logo/banner assets via vision/color quantization.
- Font licensing validation and Google Fonts availability checks.
- Full brand compliance audit that enforces approved colors/fonts after generation.
- Rich contrast-aware color/font pairing recommendations.
- Multi-brand stores and multiple brand contexts per Shopify store.
- Full brandbook/Figma/PDF import as additional discovery sources.

---

## Recommended Execution Strategy

Use coordinator mode with fresh subagents by lane:

1. Schema/persistence subagent.
2. Shopify evidence collector subagent.
3. Gemini recommendation/color subagent.
4. Font extraction/recommendation subagent.
5. Generation integration subagent.
6. Frontend discovery UI subagent.
7. Docs + final QA subagent.

Coordinator must independently review each phase, run narrow tests, and only advance after the phase passes.
