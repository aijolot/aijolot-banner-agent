# Brand Color Roles and AI Palette Suggestions Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task. Coordinator mode should dispatch fresh implementation subagents per phase, then run spec-compliance and code-quality review subagents before advancing.

**Goal:** Make Aijolot Brand Context more usable by replacing implicit palette ordering with understandable color roles, adding per-role allowed palette variants, and adding AI-assisted palette suggestions for each selected color role.

**Architecture:** Preserve the existing BrandContext API and Markdown/Supabase fallback flow, but evolve the schema in a backward-compatible way. Add explicit color role metadata (`primary`, `secondary`, `tertiary`) and variant palettes while keeping legacy `palette` available during migration. Backend owns validation, first-class Supabase persistence, Gemini-backed AI suggestion generation, and explicit unavailable/error behavior; frontend owns a clearer role-based editor and per-role suggestion UI.

**Tech Stack:** FastAPI, Pydantic v2, Supabase/Postgres, Markdown YAML frontmatter, static React UMD/Babel frontend, Google Gemini text/color suggestions via existing Gemini tooling.

---

## Current Repository Reality

Verified on 2026-06-08:

- Repo: `/Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent`
- Branch: `main` tracking `origin/main`
- Latest observed commit: `04a0b20 Merge pull request #18 from aijolot/feat/demo-functional-e2e`
- Brand model source of truth: `backend/app/schemas/brand.py`
- Brand Markdown seeds: `brands/avocado_store.md`, `brands/demo_apparel.md`, `brands/maison.md`
- Runtime brand service: `backend/app/services/brands/brand_service.py`
- Markdown importer: `backend/app/services/brands/markdown_importer.py`
- Supabase brand table/repo: `supabase/migrations/20260528190000_initial_schema.sql`, `backend/app/db/repositories/brand_contexts.py`
- Root brand API: `backend/app/api/brands.py`
- Canonical protected brand API: `backend/app/api/v1/brands.py`
- Frontend brand editor: `frontend/BrandContextView.jsx`
- Frontend offline brand seeds/API adapter: `frontend/data.jsx`
- Concept usage of brand palette/voice: `backend/app/agents/skills/banner-concept-draft/impl.py`
- Image prompt usage of palette/directives: `backend/app/agents/skills/image-prompt-refine/impl.py`
- HTML palette resolution: `backend/app/services/banners/html_renderer.py`
- Liquid payload builder: `backend/app/services/shopify/liquid_payload_builder.py`

Current behavior to preserve until migrated:

- Existing `BrandContext.palette` is a list of `{name, hex}` and is still used throughout the generation pipeline.
- Existing logic implicitly treats palette order as:
  - `palette[0]` = text / primary-ish token
  - `palette[1]` = background / secondary-ish token
  - `palette[2]` = CTA background / accent-ish token
- Frontend already edits colors, typography, voice, Shopify fields, and image directives.
- API must remain compatible with existing seeded brands and frontend fallback data.

---

## Desired Product Behavior

### New brand color model, user-facing language

Each brand gets explicit, understandable color roles:

1. **Primary color**
   - User label: “Primary”
   - Helper copy: “Main brand color. Used for dominant identity moments, headline emphasis, and major visual anchors.”
   - Agent guidance: “Prefer for main brand identity, key text/visual anchors, and high-recognition surfaces.”

2. **Secondary color**
   - User label: “Secondary”
   - Helper copy: “Support color. Used for backgrounds, secondary surfaces, and balance around the primary color.”
   - Agent guidance: “Use for background fields, supporting surfaces, and composition balance.”

3. **Tertiary color**
   - User label: “Tertiary / Accent” in English, “Terciario / Acento” in Spanish/localized UI copy
   - Helper copy: “Accent color. Used for CTA, highlights, badges, and small high-attention elements.”
   - Agent guidance: “Use sparingly for CTA, promotional badges, urgency marks, and highlights.”

### Per-role allowed palette variants

For each color role, the user can maintain a wider allowed palette/range:

- The base role color remains the canonical color.
- Each role can have allowed variants, e.g. lighter/darker/warmer/cooler options.
- Variants are explicitly allowed for content/rendering; the agent should not invent arbitrary colors outside these ranges unless the user accepts an AI suggestion.
- Each variant should have at least:
  - `name`
  - `hex`
  - optional `usage_hint`
  - optional `source` (`manual`, `ai_suggested`, `seed_migration`)

### AI Palette Suggestions button

For each color role card:

- Button label: `AI Palette Suggestions`
- Sends current brand context and selected role/color to backend.
- Backend asks AI for a variety of allowed palette variants for that role.
- AI response should return multiple suggestions with names, hex values, and usage hints.
- Frontend displays suggestions for review.
- User can accept one/many suggestions into the role’s allowed variants.
- Nothing is saved until the user clicks existing Save/Guardar flow.
- Because this is a Google Hackathon project, Gemini is required for the demo/product AI suggestion path. If Gemini/API key/budget is unavailable, the backend should fail clearly with a user-facing “Gemini unavailable” error instead of pretending suggestions were AI-generated. Deterministic color math may exist only as a unit-test helper or explicitly labeled developer fallback, not as the demo path.

---

## Proposed Data Contract

### New models in `backend/app/schemas/brand.py`

Add these models while keeping `PaletteColor`, `Typography`, `Voice`, `Shopify`, `BrandContext`, and `BrandSummary` compatible:

```python
class BrandColorVariant(BaseModel):
    name: str = Field(..., min_length=1)
    hex: str
    usage_hint: str = ""
    source: str = "manual"  # manual | ai_suggested | seed_migration

    @field_validator("hex")
    @classmethod
    def _valid_hex(cls, v: str) -> str:
        return _normalize_hex(v)


class BrandColorRole(BaseModel):
    key: str = Field(..., pattern=r"^(primary|secondary|tertiary)$")
    label: str = Field(..., min_length=1)
    hex: str
    usage_hint: str = ""
    agent_hint: str = ""
    variants: list[BrandColorVariant] = Field(default_factory=list)

    @field_validator("hex")
    @classmethod
    def _valid_hex(cls, v: str) -> str:
        return _normalize_hex(v)


class BrandColorSystem(BaseModel):
    primary: BrandColorRole
    secondary: BrandColorRole
    tertiary: BrandColorRole
```

Add to `BrandContext`:

```python
color_system: BrandColorSystem | None = None
```

Important compatibility rule:

- `palette` remains required for now.
- If old brands lack `color_system`, normalize from `palette`:
  - primary = `palette[0]`
  - secondary = `palette[1]` if present else `palette[0]`
  - tertiary = `palette[2]` if present else secondary/primary
- When saving new brands, derive/update `palette` from role colors plus selected variants so old generation code remains safe while downstream tasks migrate usage.

### Suggested role defaults

Use these default labels/hints during migration:

```python
ROLE_DEFAULTS = {
    "primary": {
        "label": "Primary",
        "usage_hint": "Main brand color for dominant identity moments, headline emphasis, and major visual anchors.",
        "agent_hint": "Prefer for main brand identity, key text/visual anchors, and high-recognition surfaces.",
    },
    "secondary": {
        "label": "Secondary",
        "usage_hint": "Support color for backgrounds, secondary surfaces, and balance around the primary color.",
        "agent_hint": "Use for background fields, supporting surfaces, and composition balance.",
    },
    "tertiary": {
        "label": "Tertiary / Accent",
        "usage_hint": "Accent color for CTA, highlights, badges, and small high-attention elements.",
        "agent_hint": "Use sparingly for CTA, promotional badges, urgency marks, and highlights.",
    },
}
```

---

## Coordinator Execution Strategy

The coordinator should not hand the whole feature to one subagent. Use phase-specific subagents, because backend schema/API, AI service, frontend UX, and generation integration touch overlapping but separable concerns.

Recommended lane split:

1. **Backend Schema + Migration Subagent**
   - Owns Pydantic models, normalization helpers, Markdown/Supabase persistence compatibility, seed migration tests.

2. **Backend AI Suggestions API Subagent**
   - Owns suggestion request/response schemas, Gemini service, explicit unavailable/error behavior, root and `/api/v1` routes, tests.

3. **Generation Integration Subagent**
   - Owns concept/image/html/liquid usage of explicit color roles while preserving old palette fallback.

4. **Frontend Brand Editor Subagent**
   - Owns role-based UI, editable hints, per-role variant editor, Gemini AI suggestions button and accept/error flow, offline brand-data fallback updates.

5. **Integration/QA Subagent**
   - Owns full route smoke, focused backend tests, frontend static checks if available, and acceptance verification.

Coordinator gates:

- **Pre-flight gate:** Before any implementation, verify branch/status and create a focused branch from `main`.
- **Revision gate after each phase:** Run narrow tests and spec review before moving on.
- **Integration gate:** Full focused backend tests plus manual/frontend smoke checklist.
- **Abort/escalation gate:** Stop and ask if a schema migration would break already-deployed data or if the desired wording/UX differs from this plan.

---

## Implementation Tasks

### Task 0: Pre-flight branch and current-state check

**Objective:** Ensure implementation starts from a safe clean branch and captures current truth.

**Files:**
- No source modifications expected.

**Steps:**

1. Run:

```bash
cd /Users/pk/Documents/Projects/freelance/hackathons/aijolot-banner-agent
git status --short --branch
git checkout main
git pull --ff-only
git checkout -b feature/brand-color-roles-ai-palettes
```

2. If uncommitted changes exist, stop and ask Pk before switching.

3. Verify:

```bash
git status --short --branch
git log --oneline -3
```

Expected:
- On `feature/brand-color-roles-ai-palettes`
- Clean working tree before code changes.

---

### Task 1: Add color role schema and normalization tests

**Objective:** Add explicit color-role models and ensure old `palette`-only brands normalize into the new color system.

**Files:**
- Modify: `backend/app/schemas/brand.py`
- Create or modify tests: `backend/tests/unit/test_brand_color_system.py`

**Test-first requirements:**

Add tests for:

1. `BrandContext` accepts existing seed-style payloads without `color_system`.
2. A helper builds `color_system` from legacy `palette` order.
3. Hex values normalize to uppercase for role colors and variants.
4. Invalid role keys fail validation.
5. A brand with explicit `color_system` preserves role labels, usage hints, agent hints, and variants.

**Implementation notes:**

- Extract `_normalize_hex(v: str) -> str` so `PaletteColor`, `BrandColorVariant`, and `BrandColorRole` share validation.
- Add helper:

```python
def ensure_color_system(brand: BrandContext) -> BrandContext:
    ...
```

or a class/model validator if cleaner with Pydantic v2.

- Keep `palette` required in the public model for now to minimize downstream breakage.
- Avoid deleting existing `PaletteColor` behavior.

**Verification:**

```bash
cd backend
. .venv/bin/activate
pytest tests/unit/test_brand_color_system.py -v
pytest tests/unit/test_brand_markdown_importer.py -v
```

Expected: all pass.

**Commit:**

```bash
git add backend/app/schemas/brand.py backend/tests/unit/test_brand_color_system.py
git commit -m "feat(brand): add explicit color role schema"
```

---

### Task 2: Persist color roles through Markdown and first-class Supabase storage

**Objective:** Ensure color role data round-trips through Markdown seeds/API saves and a scalable first-class Supabase storage shape.

**Files:**
- Modify: `backend/app/services/brands/markdown_importer.py`
- Modify: `backend/app/services/brands/brand_service.py`
- Modify: `backend/app/db/repositories/brand_contexts.py`
- Create migration: `supabase/migrations/YYYYMMDDHHMMSS_add_brand_color_system.sql`
- Modify tests:
  - `backend/tests/unit/test_brand_markdown_importer.py`
  - `backend/tests/integration/test_brand_context_repository.py`
  - `backend/tests/api/test_brands.py`

**Storage decision:**

Use a first-class `brand_contexts.color_system jsonb` column for scalability and product-readiness.

Rationale:
- This feature is core brand identity data, not import/source metadata.
- A dedicated column makes validation, indexing, query/debug tooling, analytics, future RLS policies, and product evolution cleaner.
- `source_metadata` should remain reserved for provenance/import notes and legacy compatibility.
- Keep backward compatibility by also being able to read legacy `source_metadata.color_system` if present, but always write the canonical `color_system` column going forward.
- Use `jsonb` for flexible evolution while keeping the feature first-class. Do not split roles/variants into separate relational tables in this task; that would be overkill until the product needs role-level querying, sharing, or approval workflows.

Migration requirements:

```sql
alter table public.brand_contexts
add column if not exists color_system jsonb;

create index if not exists brand_contexts_color_system_gin_idx
on public.brand_contexts using gin (color_system);
```

**Test-first requirements:**

1. Markdown importer loads a brand with `color_system` in frontmatter.
2. Markdown dumper writes `color_system` back out.
3. BrandService `_record_payload_from_brand()` writes top-level `color_system`.
4. BrandService `_brand_from_record()` restores top-level `color_system` first, then legacy `source_metadata.color_system` if needed.
5. Old records without any `color_system` still normalize from `palette`.
6. Repository `writable_columns` allows `color_system`.

**Verification:**

```bash
cd backend
. .venv/bin/activate
pytest tests/unit/test_brand_markdown_importer.py -v
pytest tests/integration/test_brand_context_repository.py -v
pytest tests/api/test_brands.py -v
# if local Supabase services are available:
supabase db reset
```

Expected: all pass.

**Commit:**

```bash
git add backend/app/services/brands backend/app/db/repositories backend/tests supabase/migrations
git commit -m "feat(brand): persist color roles across brand stores"
```

---

### Task 3: Update seeded brands with explicit color roles

**Objective:** Make the three demo brands understandable in the new role-based editor.

**Files:**
- Modify: `brands/avocado_store.md`
- Modify: `brands/demo_apparel.md`
- Modify: `brands/maison.md`
- Modify frontend fallback seeds: `frontend/data.jsx`

**Role mapping:**

Maison:
- primary: Noir base `#0B1622`
- secondary: Steel navy `#1E3A52`
- tertiary: Boss gold `#C9A24B`

Demo Apparel:
- primary: Ink `#0E0E10`
- secondary: Bone `#EDE8E0`
- tertiary: Electric `#3D5AFE`

Avocado Store:
- primary: Forest `#1F4D2E`
- secondary: Avocado `#7CB342`
- tertiary: Coral pop `#FF6B5C`

**Variant seed guidance:**

For each role, add 2-4 initial variants using existing palette colors where possible:

- include canonical role color as variant or base only, but be consistent
- include existing unused colors as variants where useful
- mark `source: seed_migration`
- write concise usage hints, e.g. “CTA hover”, “soft background”, “dark text”, “badge accent”

**Verification:**

```bash
cd backend
. .venv/bin/activate
python - <<'PY'
from app.services.brands.markdown_importer import BrandMarkdownImporter
for brand_id in ['avocado_store', 'demo_apparel', 'maison']:
    brand = BrandMarkdownImporter('../brands').load_id(brand_id)
    print(brand_id, brand.color_system.primary.hex, brand.color_system.secondary.hex, brand.color_system.tertiary.hex)
PY
```

Expected:
- All three brands load and print expected role colors.

Then run:

```bash
pytest tests/unit/test_brand_markdown_importer.py -v
```

**Commit:**

```bash
git add brands frontend/data.jsx
git commit -m "chore(brand): add role-based color systems to demo brands"
```

---

### Task 4: Add backend AI palette suggestion service

**Objective:** Provide a backend service that returns color variants for a selected brand role using Gemini. This is a Google Hackathon feature, so the user-facing/demo path must require Gemini instead of silently falling back to non-AI suggestions.

**Files:**
- Create: `backend/app/services/brands/palette_suggestions.py`
- Modify: `backend/app/schemas/brand.py` or create `backend/app/schemas/palette_suggestions.py`
- Create tests: `backend/tests/unit/test_palette_suggestions.py`

**Request shape:**

```python
class PaletteSuggestionRequest(BaseModel):
    role_key: Literal["primary", "secondary", "tertiary"]
    base_hex: str
    count: int = Field(default=8, ge=3, le=12)
    intent: str = ""
    brand_context: BrandContext
```

**Response shape:**

```python
class PaletteSuggestion(BaseModel):
    name: str
    hex: str
    usage_hint: str
    rationale: str = ""

class PaletteSuggestionResponse(BaseModel):
    role_key: str
    base_hex: str
    source: Literal["gemini"]
    suggestions: list[PaletteSuggestion]
```

**Service behavior:**

- Validate all hex outputs.
- Deduplicate suggestions by hex.
- Exclude exact duplicates already present in the selected role’s variants unless needed as canonical context.
- Include brand context in the AI prompt:
  - brand name
  - current role colors
  - existing variants
  - voice tone
  - prohibited words/required phrases only as brand context, not copy instructions
  - image style directives
  - usage intent for selected role
- Ask Gemini for practical ecommerce usage hints, not abstract names only.
- If Gemini is unavailable, return an explicit service error that the API maps to a clear 503-style user-facing response. Do not return fake “AI” suggestions.
- Deterministic color math is allowed only as a private unit-test fixture/helper for validating filtering/deduplication behavior; it must not be exposed as the demo/product suggestion source.

**Test-first requirements:**

1. Gemini prompt path builds from brand context, selected role, current colors, variants, and usage intent.
2. Suggestions are deduplicated.
3. Invalid Gemini hex values are filtered out.
4. Count is bounded.
5. Role key must be valid.
6. Missing/unavailable Gemini raises a clear service error rather than deterministic production suggestions.

**Verification:**

```bash
cd backend
. .venv/bin/activate
pytest tests/unit/test_palette_suggestions.py -v
```

**Commit:**

```bash
git add backend/app/services/brands/palette_suggestions.py backend/app/schemas backend/tests/unit/test_palette_suggestions.py
git commit -m "feat(brand): add AI palette suggestion service"
```

---

### Task 5: Add palette suggestion API routes

**Objective:** Expose AI palette suggestions through root and canonical brand APIs.

**Files:**
- Modify: `backend/app/api/brands.py`
- Modify: `backend/app/api/v1/brands.py`
- Modify tests: `backend/tests/api/test_brands.py`
- Optionally update contract docs: `docs/architecture/api-contract.md`

**Routes:**

Root prototype route:

```text
POST /brands/{brand_id}/palette-suggestions
```

Canonical protected route:

```text
POST /api/v1/brands/{brand_id}/palette-suggestions
```

**Behavior:**

- Load the persisted brand by `brand_id`.
- Merge request fields with persisted brand context.
- The request should not need to send the full brand if route can load it; allow optional draft override for unsaved frontend changes:

```python
class PaletteSuggestionRouteRequest(BaseModel):
    role_key: Literal["primary", "secondary", "tertiary"]
    base_hex: str | None = None
    count: int = 8
    intent: str = ""
    draft_brand_context: BrandContext | None = None
```

- If `draft_brand_context` is provided, use it for suggestions without saving it.
- If no `base_hex`, use the selected role’s base hex.
- `/api/v1` route must use request-scoped team service via existing `_service(request)`.
- Root route can use existing prototype `brand_store` behavior.

**Test-first requirements:**

1. Root route returns Gemini suggestions when Gemini is configured/mocked.
2. Route returns 404 for missing brand.
3. Invalid role key returns validation error.
4. Draft brand context can override persisted brand for unsaved UI colors.
5. `/api/v1` route requires auth/request context consistent with existing v1 tests.
6. Missing Gemini configuration or Gemini service failure returns a clear 503-style error and does not return deterministic suggestions.

**Verification:**

```bash
cd backend
. .venv/bin/activate
pytest tests/api/test_brands.py -v
pytest tests/api/test_api_v1_contract.py -v
```

**Commit:**

```bash
git add backend/app/api/brands.py backend/app/api/v1/brands.py backend/tests/api docs/architecture/api-contract.md
git commit -m "feat(api): expose brand palette suggestions"
```

---

### Task 6: Integrate color roles into concept/image/html/liquid generation

**Objective:** Make the agent use explicit role semantics instead of relying only on palette order, while preserving old fallback.

**Files:**
- Modify: `backend/app/agents/skills/banner-concept-draft/impl.py`
- Modify: `backend/app/agents/skills/image-prompt-refine/impl.py`
- Modify: `backend/app/services/banners/html_renderer.py`
- Modify: `backend/app/services/shopify/liquid_payload_builder.py`
- Add/modify tests around concept/html/liquid rendering if existing nearby tests exist.

**Implementation guidance:**

Create helper functions near usage sites or a shared utility if reuse is cleaner:

```python
def brand_color_roles(brand: Any) -> dict[str, dict[str, Any]]:
    ...
```

Concept drafting should use:

- text/main identity token = primary
- background/support token = secondary
- CTA/accent token = tertiary

But be careful with contrast:
- Do not assume primary is readable over secondary.
- Preserve existing contrast/review behavior where available.
- If contrast helper exists, use it; otherwise keep current behavior and log follow-up gap.

Image prompt should mention:
- role labels
- base hexes
- variant hexes if present
- usage hints/agent hints

Allowed variants should affect generation immediately:
- Treat `color_system.<role>.variants` as the approved color range for that role.
- Concept/palette selection may choose a base role color or one of its accepted variants based on placement, contrast, and creative fit.
- Do not invent non-approved colors when a role has variants; if contrast requires adjustment, pick from approved variants first and record a carry-over gap only if none are usable.
- Persist/emit which role variant was selected in concept metadata when practical, so frontend/debug views can explain why a generated banner used that color.

HTML renderer should resolve palette usage from roles first, then legacy palette lookup.

Liquid config should include:

```json
"color_system": {
  "primary": {...},
  "secondary": {...},
  "tertiary": {...}
}
```

and, if safe in current section style, expose CSS variables/settings for role colors. If this is too large for this feature, record as carry-over but at least include role data in config.

**Test-first requirements:**

1. Concept palette usage uses role names/keys when `color_system` exists.
2. Legacy palette-only brand still produces old expected behavior.
3. Image prompt includes role/variant color values.
4. HTML renderer resolves colors from color system.
5. Liquid config includes color system.
6. At least one generation/concept test proves accepted variants are eligible for use, not merely stored.

**Verification:**

```bash
cd backend
. .venv/bin/activate
pytest tests/unit -k "brand or concept or liquid or html" -v
```

Then run a small direct smoke similar to:

```bash
python - <<'PY'
# Load Maison, draft concept, render prompt, print palette usage and prompt snippets.
PY
```

**Commit:**

```bash
git add backend/app/agents/skills backend/app/services/banners/html_renderer.py backend/app/services/shopify/liquid_payload_builder.py backend/tests
git commit -m "feat(agent): use explicit brand color roles in generation"
```

---

### Task 7: Redesign frontend brand color editor around roles and variants

**Objective:** Replace the single flat palette editor UX with role cards for Primary, Secondary, and Tertiary, each with base color, usage hints, allowed variants, and AI suggestions button.

**Files:**
- Modify: `frontend/BrandContextView.jsx`
- Modify: `frontend/data.jsx`
- Optional helper file only if frontend structure already supports it; otherwise keep static prototype style.

**UI requirements:**

For each role card:

- Title: Primary / Secondary / Tertiary / Accent
- Base color swatch and hex input
- Editable user-facing helper copy from role `usage_hint`
- Editable agent hint text, shown as smaller “Agent guidance” / advanced field
- Variant list:
  - name input
  - hex input/color picker
  - usage hint input
  - delete button
- Add manual variant button
- `AI Palette Suggestions` button
- Suggestions tray/state:
  - loading spinner
  - error message
  - list of suggested swatches with name, hex, usage hint/rationale
  - accept button per suggestion
  - accept all button if useful

Interaction rules:

- Accepted suggestions are appended to `draft.color_system[role].variants` with `source: "ai_suggested"`.
- Suggestions do not auto-save.
- Existing `dirty` detection should catch accepted suggestions.
- Existing Save button persists the whole brand.
- If backend/Gemini is unavailable, show the clear backend error and do not generate local deterministic “AI” suggestions. The hackathon demo path should prove Gemini usage.

**Data adapter updates:**

- Add `BrandAPI.paletteSuggestions(id, payload)` in `frontend/data.jsx`.
- It should call:

```js
AijolotApi.post(AijolotApi.v1(`/brands/${id}/palette-suggestions`), payload)
```

- If network unreachable, set `BrandAPI.online = false` and surface a clear “backend/Gemini suggestions unavailable” message.
- If backend returns a real HTTP error, surface it.

**Preview update:**

- Update `paletteToVars` / `brandToSeg` to prefer `draft.color_system` roles over flat `palette`.
- Keep legacy fallback to `palette` for old data.

**Verification:**

Manual/static smoke checklist:

1. Brand tab loads with three role cards for each seed brand.
2. Editing primary/secondary/tertiary base colors updates preview.
3. Adding/removing variants marks draft dirty.
4. AI Palette Suggestions returns Gemini-backed suggestions and accept works.
5. Save sends `color_system` in payload.
6. Offline fallback still shows demo seed brands, but AI suggestions are disabled/unavailable instead of faked.

If package scripts exist, run relevant frontend checks. If no build/lint script exists, record that frontend is static UMD/Babel and verify by browser/manual smoke.

**Commit:**

```bash
git add frontend/BrandContextView.jsx frontend/data.jsx
git commit -m "feat(frontend): edit brand color roles and AI palette variants"
```

---

### Task 8: Documentation and API contract update

Status note (2026-06-09): Completed documentation pass on the feature branch. Added the dedicated brand color system architecture doc, updated API contract with `color_system` and palette suggestion routes, and refreshed frontend integration handoff for role-based brand colors and Gemini-only suggestion behavior.

**Objective:** Document the new color-role brand context behavior for backend, frontend, and future agent work.

**Files:**
- Modify: `docs/architecture/api-contract.md`
- Create or modify: `docs/architecture/brand-context-color-system.md`
- Optionally modify: `docs/architecture/frontend-integration-function-reference.md` if current handoff expects brand routes.

**Content requirements:**

Document:

- `BrandContext.color_system` shape
- legacy `palette` compatibility
- role semantics and usage expectations
- palette suggestion endpoint request/response
- Gemini requirement and explicit unavailable/error behavior
- frontend usage rules
- generation usage rules
- known limitations/carry-over gaps

Known carry-over candidates to include if not solved in this implementation:

- Full brand compliance audit gate for output colors/phrases/directives.
- Strong contrast-aware auto-selection of role variants.
- Logo usage integration.
- Richer import from brandbook/Figma.

**Verification:**

```bash
git diff --check
```

Read docs for consistency with implemented schemas/routes.

**Commit:**

```bash
git add docs/architecture
git commit -m "docs: document brand color system and palette suggestions"
```

---

### Task 9: Final integration verification and review

Status note (2026-06-09): Completed final coordinator verification. Local Supabase migration reset passed; backend deterministic suite passed (`408 passed, 3 skipped, 3 warnings`); frontend static checks passed (`node --check` for `data.jsx`, `esbuild` bundle check for `BrandContextView.jsx`); local backend/frontend smoke checks passed; live Gemini palette suggestions returned HTTP 200 for root and `/api/v1`; final review subagent found no Critical or Important blockers.

**Objective:** Prove the feature works end-to-end and is ready for demo/testing.

**Files:**
- No planned code changes unless defects are found.

**Coordinator steps:**

1. Run backend focused tests:

```bash
cd backend
. .venv/bin/activate
pytest tests/unit/test_brand_color_system.py -v
pytest tests/unit/test_palette_suggestions.py -v
pytest tests/unit/test_brand_markdown_importer.py -v
pytest tests/api/test_brands.py -v
pytest tests/api/test_api_v1_contract.py -v
```

2. Run broader brand/generation relevant tests:

```bash
pytest tests/unit -k "brand or palette or concept or liquid or html" -v
pytest tests/api -k "brand" -v
```

3. Run full backend suite if time permits:

```bash
pytest -v
```

4. Run diff hygiene:

```bash
git diff --check
git status --short
```

5. Coordinator dispatches final integration review subagent:

- Review schema backward compatibility.
- Review `/api/v1` auth/team scoping for the new endpoint.
- Review frontend offline fallback and save semantics.
- Review generation role fallback for old brands.
- Review no secrets/logging issues.

6. Fix any Critical/Important findings, rerun narrow tests, and rerun final review until approved.

**Final commit if fixes happened:**

```bash
git add -A
git commit -m "fix(brand): address color role integration review"
```

---

## Acceptance Criteria

Backend:

- Existing seeded brands and old API payloads still validate.
- New BrandContext supports explicit primary/secondary/tertiary roles.
- Role color hexes and variant hexes validate and normalize.
- Markdown import/export round-trips `color_system`.
- Brand service persists/restores color roles in fallback and Supabase-backed modes.
- Palette suggestion service returns valid, deduped Gemini-backed suggestions and fails clearly when Gemini is unavailable.
- Root and `/api/v1` suggestion routes work and respect existing auth/team boundaries.

Generation:

- Concept drafting uses role semantics instead of raw palette indexes when `color_system` exists.
- Image prompts include role colors and allowed variants.
- Accepted variants are actively eligible for generation/color selection, not just stored.
- HTML preview resolves role colors.
- Liquid config carries role color data.
- Legacy palette-only brands still work.

Frontend:

- Brand editor shows Primary, Secondary, and Tertiary role cards.
- Each role supports base color and allowed variants.
- AI Palette Suggestions works per role.
- Accepted suggestions remain draft-only until Save.
- Preview updates from role colors.
- Offline fallback remains usable and clearly labeled.

Process:

- Implementation happens on a focused feature branch.
- Each phase is implemented by a fresh subagent and reviewed before proceeding.
- Tests and final verification output are captured before reporting completion.

---

## Decisions Confirmed by Pk Before Implementation

1. User-facing third color label should be localized by UI language. Use “Tertiary / Accent” in English and “Terciario / Acento” in Spanish/localized copy.
2. AI suggestions must use Gemini for the hackathon demo/product path. Do not silently substitute deterministic suggestions when Gemini is unavailable.
3. Allowed variants should be actively used by generation because they represent accepted palettes/ranges for brand content.
4. `color_system` should be treated as scalable product data, so use a first-class Supabase `jsonb` column instead of burying it in `source_metadata`.
5. Role hints should be editable in the UI, including practical user-facing usage hints and agent guidance.

## Remaining Definition Needed Before Execution

No hard blockers remain for coordinator-mode execution. Before starting implementation, the coordinator should only verify environment readiness:

- Gemini API key/config is available for the backend demo path, because this feature should not fake AI suggestions.
- Local Supabase can run/reset for the migration task, or the coordinator should mark DB reset as an environment blocker and still run unit/API tests that do not require live Supabase.
- Pk is okay with the focused branch name `feature/brand-color-roles-ai-palettes`; otherwise rename it during Task 0.

---

## Notes for Implementation Subagents

- Do not remove legacy `palette` during this feature.
- Do not break root prototype routes.
- Do not bypass `/api/v1` request context on canonical routes.
- Do not read or print secrets.
- Do not fake AI palette suggestions. Gemini-backed suggestions are required for the demo/product path; if unavailable, fail clearly.
- Keep changes scoped to brand color usability and palette suggestions; do not implement full brand compliance auditing in this phase unless Pk explicitly expands scope.
