# Brand discovery and font system

This document is the working contract for Shopify brand discovery and the approved-font typography system. It complements `docs/architecture/api-contract.md`, `docs/architecture/brand-context-color-system.md`, and the Pydantic models in `backend/app/schemas/brand.py` and `backend/app/schemas/brand_discovery.py`.

Core principle: discovery evidence is not approved brand context. Shopify-derived raw evidence and Gemini-backed recommendation drafts are stored separately from `BrandContext`; nothing becomes active until the user explicitly accepts it (colors into `color_system` roles, fonts into `typography`).

## Overview and flow

```text
                 POST /brands/{id}/discovery-runs (synchronous)
                                  |
                                  v
+------------------+   +----------------------------+   +--------------------------+
| Shopify Admin API|-->| shopify_discovery collector |-->| BrandDiscoverySnapshot   |
| (read-only,      |   | (allowlists, byte caps,     |   | raw evidence + provenance|
|  guarded sources)|   |  per-source error guards)   |   | + confidence + errors    |
+------------------+   +----------------------------+   +-----------+--------------+
                                                                     |
                              persisted to brand_discovery_runs row  |
                              + mirrored to brand_contexts           |
                                .discovery_snapshot (latest)         |
                                                                     v
        POST .../discovery-runs/{run_id}/recommendations   POST /brands/{id}/font-suggestions
                       (Gemini-only, 503 when down)         (Gemini or labeled non-AI fallback)
                                  |                                  |
                                  v                                  v
                  +-------------------------------+   +-----------------------------+
                  | BrandRecommendationDraft      |   | FontSuggestionResponse      |
                  | color roles + rationale +     |   | discovered / suggestions /  |
                  | evidence refs (draft only)    |   | seeds (all status=candidate)|
                  +---------------+---------------+   +--------------+--------------+
                                  |                                  |
                                  +------ USER IS THE APPROVAL GATE -+
                                  |                                  |
                                  v                                  v
            UI path: accumulate accepted items into the local draft, persist with
            PUT /brands/{id}.  API path: POST /brands/{id}/apply-discovery-recommendations
                                  |
                                  v
                  +------------------------------------------+
                  | BrandContext (approved settings)         |
                  | color_system roles + palette[0..2] sync  |
                  | typography: roles + approved/discarded   |
                  +---------------------+--------------------+
                                        |
                                        v
            Generation surfaces (approved fonts/colors only, safe fallbacks):
            concept hierarchy notes, image prompt aesthetic, HTML renderer,
            Liquid config.typography + --aijolot-font-* CSS vars
```

Discovery is synchronous in the first implementation: `POST /brands/{brand_id}/discovery-runs` runs the collector inline and returns the completed run (`succeeded`, `partial`, or `failed`). There is no polling loop; `GET .../discovery-runs/{run_id}` exists for history/debugging.

## Data contracts

### BrandDiscoverySnapshot (raw evidence)

Source: `backend/app/schemas/brand_discovery.py`. Stored on the run row and mirrored to `brand_contexts.discovery_snapshot`. Never exposed on `BrandContext` itself.

```ts
type BrandDiscoverySnapshot = {
  id: string;                      // "disc_<12 hex>"
  brand_id: string;
  store_id?: string | null;
  shop_domain: string;
  status: "pending" | "running" | "succeeded" | "failed" | "partial";
  discovered_at: string;           // ISO datetime
  source_summary: string;          // human-readable per-bucket counts
  assets: BrandDiscoveryAsset[];
  colors: DiscoveredColor[];
  fonts: DiscoveredFont[];
  theme_metadata: Record<string, unknown>; // shop_name, brand_slogan, theme_name, theme_id, ...
  errors: string[];                // per-source failure messages, never raised
};

type BrandDiscoveryAsset = {
  kind: "logo" | "banner" | "hero" | "theme_asset" | "css" | "settings" | "unknown";
  url?: string | null;             // https URLs only; shopify:// refs stay in metadata.raw_ref
  shopify_gid?: string | null;
  theme_asset_key?: string | null;
  content_type?: string | null;
  source: string;                  // provenance, e.g. "shop_metadata", "css:assets/base.css"
  metadata: Record<string, unknown>;
};

type DiscoveredColor = {
  hex: string;                     // normalized uppercase #RRGGBB
  name: string;
  source: string;                  // provenance string
  confidence: number;              // 0..1 heuristic by evidence source
  usage_hint: string;
};

type DiscoveredFont = {
  family: string;                  // whitelist-normalized family name
  source: string;
  css_stack: string;               // may be empty for raw evidence
  confidence: number;              // 0..1
  sample_usage: string;
};
```

### Discovery run payload

Source: `BrandDiscoveryRunPayload` in `backend/app/services/brands/brand_discovery_service.py`. Returned by all `discovery-runs` routes.

```ts
type BrandDiscoveryRunPayload = {
  id: string;                      // run UUID
  brand_id: string;
  store_id?: string | null;
  status: "pending" | "running" | "succeeded" | "failed" | "partial";
  snapshot?: BrandDiscoverySnapshot | null;
  recommendation: Record<string, unknown>; // {} until the recommendations step attaches a draft
  created_at?: string | null;
  updated_at?: string | null;
};
```

### BrandRecommendationDraft (Gemini color role draft)

Attached to the run's `recommendation` field by `POST .../recommendations`. Draft only; nothing is applied automatically.

```ts
type BrandRecommendationDraft = {
  colors: BrandColorRecommendation[];  // exactly primary/secondary/tertiary after backfill
  fonts: FontCandidate[];              // currently always [] (fonts use /font-suggestions)
  summary: string;
  source_notes: string[];              // snapshot buckets that fed the prompt, e.g. ["theme_settings", "css"]
};

type BrandColorRecommendation = {
  role_key: "primary" | "secondary" | "tertiary";
  base_hex: string;                    // uppercase #RRGGBB
  label: string;
  usage_hint: string;
  agent_hint: string;
  variants: BrandColorVariant[];       // recommendation variants carry source: "gemini"
  rationale: string;                   // "kept from existing approved brand context" marks non-AI backfill
  evidence_refs: string[];             // canonicalized against real snapshot sources
};
```

### FontCandidate and Typography

Source: `backend/app/schemas/brand.py`. `Typography` keeps the legacy `display`/`body` strings and adds optional roles plus the approved/discarded font system.

```ts
type FontCandidate = {
  family: string;                  // letters/digits/spaces/hyphens only (whitelist-validated)
  css_stack: string;               // family chars + commas/quotes only; never empty
  category: "sans" | "serif" | "display" | "mono" | "handwritten" | "unknown";
  source: "shopify_theme" | "storefront_css" | "gemini_suggested" | "system_seed" | "manual";
  status: "candidate" | "approved" | "discarded";
  recommended_roles: Array<"display" | "headline" | "body" | "accent" | "caption">;
  rationale: string;
  evidence_refs: string[];
};

type Typography = {
  display: string;                 // legacy, default "Space Grotesk"
  body: string;                    // legacy, default "Inter"
  headline?: string | null;        // optional role assignment
  accent?: string | null;          // optional role assignment
  approved_fonts: FontCandidate[]; // status "approved"
  discarded_fonts: FontCandidate[];// status "discarded"; persisted so families are never re-suggested
};
```

Role values (`display`/`body`/`headline`/`accent`) accept the stack character rule (commas/quotes allowed) so historical values like `"Helvetica Neue, sans-serif"` stay valid while CSS injection stays blocked.

### ApplyDiscoveryRecommendationsRequest

Source: `backend/app/schemas/brand_recommendations.py`. The body lists ONLY user-accepted items; anything omitted keeps its current value.

```ts
type ApplyDiscoveryRecommendationsRequest = {
  run_id?: string | null;                       // provenance only
  colors?: BrandColorRecommendation[];          // accepted roles, with ONLY the accepted variants
  logo_url?: string | null;                     // null/empty = not accepted
  image_style_directives?: string[] | null;     // null keeps; a list (even []) replaces
  approved_fonts?: FontCandidate[];
  discarded_fonts?: FontCandidate[];
  typography_roles?: Record<string, string> | null; // display|headline|body|accent -> approved family
};
```

Response: the saved `BrandContext` (same shape as `PUT /brands/{id}`). An empty body is a validated no-op.

## Shopify evidence sources and safety caps

The collector (`backend/app/services/brands/shopify_discovery.py`) reads only the Shopify Admin API through the configured client. No arbitrary external URL is ever fetched; discovered image URLs are recorded, not downloaded.

| # | Source | What is extracted | Confidence |
| --- | --- | --- | --- |
| 1 | Shop metadata GraphQL (`shop { name primaryDomain brand { ... } }`) | Brand primary/secondary colors (background/foreground), logo/squareLogo/coverImage https URLs, slogan/short description, shop name/domain into `theme_metadata` | 0.95 |
| 2 | Main (published) theme | `theme_name`, `theme_role`, `theme_id` into `theme_metadata`; gates all theme-asset sources | n/a |
| 3 | `config/settings_data.json` + `config/settings_schema.json` | Hex colors, Shopify `font_picker` values (`helvetica_n4` -> `Helvetica`), font stacks, logo image refs, hero/banner/slideshow section markers and image refs | 0.9 (settings_data) / 0.5 (schema defaults) |
| 4 | CSS assets (`assets/*.css`, `*.css.liquid`, `*.scss.liquid`) | CSS color custom properties, raw hex colors, `font-family` declarations, font custom properties | 0.6 (variables/fonts) / 0.4 (raw hex) |
| 5 | Allowlisted section/layout Liquid files | https image URLs, `'name.png' \| asset_url` references mapped to logo/hero/banner kinds | n/a (assets only) |

Caps and allowlists:

| Cap | Value | Behavior |
| --- | --- | --- |
| Per-asset byte cap | 256 KB (`DEFAULT_MAX_ASSET_BYTES`) | Oversized assets are skipped with an error entry; oversized CSS is not even selected. |
| CSS assets per run | 5 (`DEFAULT_MAX_CSS_ASSETS`) | Selection prefers keys containing `base`/`theme`/`main`/`style`/`global`. |
| Section/layout files per run | 6 (`MAX_SECTION_ASSETS`) | Fixed allowlist `sections/header.liquid`, `sections/hero.liquid`, `sections/image-banner.liquid`, `sections/slideshow.liquid`, `layout/theme.liquid` plus `sections/hero*.liquid` globs. |
| External fetches | 0 | Only Shopify Admin API calls; image URLs are evidence, not downloads. |

Hardening rules:

- Every source is independently guarded: a failing source appends a human-readable message to `snapshot.errors` and the run degrades instead of raising. Access tokens are never read, logged, or embedded in errors/snapshots.
- Extracted fonts pass the same whitelist validators as the brand schema; CSS junk (`var(...)`, `!important`, injection attempts) is parsed down to clean families or dropped. Generic-only stacks (`sans-serif` alone) map to nothing.
- Colors/fonts/assets are deduped (highest-confidence entry wins; names/stacks are merged from duplicates).

Run status semantics:

| Status | Meaning |
| --- | --- |
| `succeeded` | No source errors. |
| `partial` | Errors occurred but some evidence (colors/fonts/assets/theme metadata) was collected. |
| `failed` | Errors and nothing could be fetched, or the collector crashed (defense-in-depth snapshot records the error). |
| `pending` / `running` | Exist in the status literal and DB check constraint; the synchronous run only exposes them transiently. |

## AI behavior and unavailable states

AI honesty contract: anything presented as AI is Gemini-backed. Deterministic content is allowed only when explicitly labeled non-AI.

| Endpoint | AI source | When Gemini is unavailable | Non-AI content in response |
| --- | --- | --- | --- |
| `POST .../palette-suggestions` | Gemini (`source: "gemini"`) | `503` with clear detail; never fake suggestions | None |
| `POST .../discovery-runs/{run_id}/recommendations` | Gemini (`BrandRecommendationDraft`) | `503`; the draft is never faked | Per-role backfill from the user's own approved color system when Gemini answers with fewer than three roles, labeled `rationale: "kept from existing approved brand context"` with empty `evidence_refs` |
| `POST .../font-suggestions` | Gemini (`source: "gemini"`, `ai_available: true`) | `200` with `source: "deterministic_fallback"`, `ai_available: false`, `suggestions: []`, and a message explaining the fonts below are not AI recommendations | `discovered` (deterministic snapshot mapping, sources `shopify_theme`/`storefront_css`) and `seeds` (curated `system_seed` pool) are always non-AI labeled |

Additional Gemini recommendation rules (`backend/app/services/brands/brand_recommendations.py`):

- The prompt includes discovered colors sorted by confidence, shop/theme metadata, asset summary, and the existing approved color system with an explicit instruction to refine rather than overwrite it.
- Gemini output is parsed tolerantly, then converted to the strict schema: invalid hexes drop the item, duplicate role keys keep the first valid one, variants are deduped against the base hex and capped at 6 per role, and `evidence_refs` are canonicalized against actual snapshot sources (fall back to the sources that produced the recommended hex). If no role survives, the route returns `503` ("no valid color role recommendations").
- Recommendation variants carry `source: "gemini"`.

Font suggestion rules (`backend/app/services/brands/font_suggestions.py`):

- Discarded families are forbidden in the prompt AND filtered from the parsed output; discovered/approved families are never re-suggested as new AI suggestions (complements/pairings instead).
- A bad AI `css_stack` is rebuilt from the family/category once before the family is dropped; unsafe families are dropped entirely.
- Seeds exclude families the user already approved/discarded (and, on the AI path, families Gemini just suggested).

## Apply/approval semantics

The user is the approval gate. `POST /brands/{brand_id}/apply-discovery-recommendations` merges ONLY the listed items (merge logic: `backend/app/services/brands/apply_recommendations.py`):

- Colors: each accepted `BrandColorRecommendation` replaces its role wholesale (label, hex, usage/agent hints, variants; variant `source` preserved as provided). Roles not listed stay exactly as they are, including their variants.
- Palette sync: when at least one color is accepted, legacy `palette[0..2]` is re-synced to the three role colors post-merge (same rule as the frontend `syncPaletteFromColorSystem`); entries beyond index 2 are preserved as extras so old generation paths keep working.
- Fonts: `approved_fonts` upsert into `typography.approved_fonts` (dedupe by lowercased family, replacing in place) with `status` forced to `"approved"`. `discarded_fonts` are removed from approved and upserted into `typography.discarded_fonts` with `status` `"discarded"`. An explicit approval symmetrically reverses an earlier discard of the same family. Approving AND discarding one family in the same request is a `422`.
- `typography_roles`: assigns `display`/`headline`/`body`/`accent` to an approved family, validated against the post-merge approved list (canonical casing taken from the approved entry). Unknown role keys or unapproved families return `422`. `caption` is a recommendation role only; it has no `Typography` field. `display`/`body` keep their current values when not assigned -- they are never emptied implicitly.
- `logo_url` is set only when provided and non-empty; `image_style_directives: null` keeps the current list while a list (even `[]`) replaces it.
- The merged brand is fully re-validated through `BrandContext.model_validate` before persisting; an empty request returns the current brand without a write.

Who calls it: this endpoint exists for API consumers. The shipped UI does NOT use it -- the Brand Context editor accumulates accepted items into its local draft and persists everything through the normal `PUT /brands/{id}` save flow (see Frontend integration below). Both paths converge on the same saved `BrandContext` shape.

## Font candidate lifecycle

```text
                       +--> approved  (typography.approved_fonts, status="approved")
candidate (draft) -----|        ^  |
                       |        |  v   (approve reverses discard; discard removes from approved)
                       +--> discarded (typography.discarded_fonts, status="discarded")
```

- Candidates come from four places, all with provenance in `source`: deterministic snapshot mapping (`shopify_theme`, `storefront_css`), Gemini (`gemini_suggested`), the curated seed pool (`system_seed`), and manual entry (`manual`).
- Nothing returned by discovery/suggestions is auto-approved: every candidate ships with `status: "candidate"`.
- `family` and `css_stack` are whitelist-validated (letters/digits/spaces/hyphens for families; plus commas/quotes for stacks). The whitelist provably rejects `< > { } ; ( ) & \ / @` and control characters, so `url(`, `expression(`, and `@import` cannot appear -- injection-safe by construction, at the schema layer and re-checked at generation time.
- Discards persist on the brand. Suggestion services read `typography.discarded_fonts` and never re-offer those families (prompt rule + output filter + seed exclusion).
- Approved fonts dedupe by lowercased family; re-approving an existing family replaces its entry in place.

The curated `SYSTEM_SEED_FONTS` pool (16 families in `backend/app/services/brands/font_discovery.py`) is always labeled `system_seed` with rationale prefix `"Curated seed (non-AI):"`.

## Generation usage rules

All generation surfaces resolve fonts through `backend/app/services/brands/font_roles.py`, which tolerates both `BrandContext` models and plain dicts and degrades to `""`/`{}` so callers keep their legacy defaults.

`resolve_font_stack(brand, role)` resolution chain:

1. The typography role value, with role fallbacks: `headline -> display`, `accent -> headline -> display`, `caption -> body`.
2. If the value matches an approved font family (case-insensitive, status `approved`), the candidate's `css_stack` wins (rebuilt from family/category if the stored stack is broken/unsafe).
3. Else a comma in the value means it already is a stack and is used as-is.
4. Else a single family gets a generic fallback via `build_css_stack` (category-guessed generic).
5. Every emitted stack passes `quote_stack` (multi-word families double-quoted) and a defensive character whitelist; unsafe values resolve to `""` (missing).

Per surface:

- HTML renderer (`backend/app/services/banners/html_renderer.py`): `body` stack replaces the hardcoded body `font-family`; a resolved `display` stack adds an `h1,.aij-eyebrow {font-family:...}` rule. Empty resolutions keep today's hardcoded defaults byte-for-byte, so legacy brands render identically.
- Liquid payload (`backend/app/services/shopify/liquid_payload_builder.py`): the config JSON gains a `typography` block (`{stacks, approved_fonts (family/category/recommended_roles only), legacy: {display, body}}`), and the section `style` attribute gains `--aijolot-font-<role>` CSS variables for resolved stacks. Double quotes inside stacks are swapped to single quotes so the double-quoted `style` attribute stays valid.
- Concept skill (`backend/app/agents/skills/banner-concept-draft/impl.py`): `hierarchy_notes` gains a `Typography: <role>: <family> (approved, <category>|legacy), ...` line via `font_prompt_lines` (only roles with a direct value; inherited fallbacks are not repeated).
- Image prompts (concept + `image-prompt-refine`): only the category-derived aesthetic phrase from `font_aesthetic_hint` (e.g. "geometric sans-serif aesthetic") may appear. Font NAMES never enter image prompts -- generated imagery stays text/mark-free, and the phrases avoid image-sanitizer-forbidden terms.

## Storage layout

Migration: `supabase/migrations/20260610005446_add_brand_discovery_and_typography.sql`.

`brand_contexts` gains two first-class JSONB columns (both GIN-indexed):

- `discovery_snapshot`: the latest `BrandDiscoverySnapshot` for the brand (raw evidence; mirrored after every run so the editor can show the most recent state without a run id).
- `typography_system`: the FULL `Typography` dump (display/body/headline/accent/approved_fonts/discarded_fonts). The legacy `typography` column keeps the historical two-key `{display, body}` shape so old readers stay stable. Reads prefer `typography_system` and fall back to the legacy column.

`brand_discovery_runs` keeps per-run history for debuggability/audits:

```sql
create table if not exists public.brand_discovery_runs (
  id uuid primary key default gen_random_uuid(),
  team_id text not null,
  store_id text,
  brand_id text not null,         -- runtime brand slug (BrandContext.id)
  status text not null check (status in ('pending', 'running', 'succeeded', 'failed', 'partial')),
  snapshot jsonb not null default '{}'::jsonb,
  recommendation jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

Indexed on `(team_id, brand_id, created_at desc)` with an `updated_at` trigger. RLS is enabled with no anon/authenticated policies on purpose: backend access goes through the service-role client only, because raw discovery evidence is team-internal.

Discovery requires Supabase runtime storage. Without it the service raises `DiscoveryPersistenceUnavailable` (`503`): discovery runs are never tracked in-memory or faked offline. Similarly, without Shopify Admin credentials the run returns `503` (`DiscoveryUnavailable`) instead of fabricating evidence.

## API surface

Full request/response examples live in `docs/architecture/api-contract.md`. Summary:

```text
POST /api/v1/brands/{brand_id}/discovery-runs                              (synchronous run)
GET  /api/v1/brands/{brand_id}/discovery-runs/{run_id}                     (run history/detail)
POST /api/v1/brands/{brand_id}/discovery-runs/{run_id}/recommendations     (Gemini color role draft)
POST /api/v1/brands/{brand_id}/font-suggestions                            (font candidates)
POST /api/v1/brands/{brand_id}/apply-discovery-recommendations             (explicit merge)
```

`/api/v1` routes require the demo auth/team context and fail closed with `401`; the discovery service, brand service, and run repository are scoped to the request team (a run reached through another team or another brand's URL behaves as not found). Root-level mirrors of all five routes exist for prototype compatibility only.

## Security and boundaries

- No token/secret logging: the collector never reads or embeds access tokens; error strings carry exception messages only.
- No arbitrary external fetches: only Shopify Admin API calls; discovered URLs are stored as evidence, not retrieved.
- Allowlists + byte caps bound every theme read (see caps table above).
- Fail-closed unavailability: Shopify missing -> `503`, Supabase missing -> `503`, Gemini missing -> `503` for color recommendations / labeled non-AI `200` for font suggestions. Nothing is silently faked.
- Tenancy: v1 discovery routes resolve the team from `require_user_context`; run reads filter by `team_id` and verify the path `brand_id` matches the run. Optional `store_id` on run creation is validated against the request team's stores (`404` otherwise).
- Injection safety: font families/stacks are whitelist-validated at the schema layer and re-sanitized at generation time (dict-shaped brands bypass Pydantic, so `font_roles` treats unsafe values as missing instead of letting them reach CSS/Liquid output).
- Discovery evidence never auto-applies: `BrandContext` has no `discovery_snapshot` field; only the explicit apply/save paths mutate approved settings.

## Frontend integration

Reference: `docs/architecture/frontend-integration-function-reference.md` (`BrandAPI.startDiscovery` / `discoveryRecommendations` / `fontSuggestions`) and `frontend/BrandContextView.jsx` (`BrandDiscoveryCard`, `TypographyCard`).

- The UI accumulates accepted items into the local brand draft and persists everything through the normal Save (`Guardar cambios`) -> `PUT /brands/{id}` flow; it does not call `apply-discovery-recommendations`.
- Draft variant provenance values: a discovered color accepted as a role variant gets `source: "shopify_discovery"`; a variant accepted from an AI recommendation gets `source: "ai_suggested"`; manual edits get `source: "manual"`. (Backend recommendation payloads themselves carry `source: "gemini"` on variants; the UI relabels on accept.)
- Discovery/AI states are never faked offline: when the backend is unreachable the UI surfaces explicit Spanish errors ("El descubrimiento requiere el backend y Shopify conectados. No se puede simular.") instead of falling back to seeds.

## Known gaps and future enhancements

Carried over from the implementation plan plus gaps confirmed during implementation:

- True async/background discovery jobs with progress streaming (current runs are synchronous; long themes block the request).
- Screenshot/visual extraction from live storefront pages.
- Image-based color extraction from logo/banner assets via vision/color quantization (asset URLs are collected but pixels are never analyzed).
- Font licensing validation and Google Fonts availability checks for approved/suggested families.
- Full brand compliance audit that enforces approved colors/fonts after generation.
- Rich contrast-aware color/font pairing recommendations.
- Multi-brand stores and multiple brand contexts per Shopify store.
- Full brandbook/Figma/PDF import as additional discovery sources.
- The campaign-level typography allowlist (`DISPLAY_FONTS`/`BODY_FONTS` in `backend/app/schemas/typography.py`, used by the canvas/art-direction concept path) is not bridged to brand-approved fonts: a campaign concept may still pick a curated allowlist font that the brand never approved.
