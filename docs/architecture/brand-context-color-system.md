# Brand context color system

This document is the working contract for Aijolot brand colors after the explicit color-role feature. It complements `docs/architecture/api-contract.md` and the Pydantic models in `backend/app/schemas/brand.py`.

## Data model

`BrandContext` still includes the legacy flat `palette`, and now also includes `color_system`:

```ts
type BrandContext = {
  id: string;
  name: string;
  palette: Array<{ name: string; hex: string }>;
  color_system?: BrandColorSystem | null;
  typography?: {
    display?: string;
    body?: string;
    // Optional role assignments + approved/discarded font system live here too;
    // see docs/architecture/brand-discovery-and-font-system.md.
    headline?: string | null;
    accent?: string | null;
    approved_fonts?: FontCandidate[];
    discarded_fonts?: FontCandidate[];
  };
  voice?: {
    tone?: string[];
    prohibited_words?: string[];
    required_phrases?: string[];
  };
  logo_url?: string | null;
  image_style_directives?: string[];
  shopify: {
    store_domain: string;
    theme_id?: string | null;
    default_placement?: string;
  };
  notes?: string;
};

type BrandColorSystem = {
  primary: BrandColorRole;
  secondary: BrandColorRole;
  tertiary: BrandColorRole;
};

type BrandColorRole = {
  key: "primary" | "secondary" | "tertiary";
  label: string;
  hex: string;              // normalized to uppercase #RRGGBB
  usage_hint?: string;      // user-facing guidance
  agent_hint?: string;      // generation/planning guidance
  variants?: BrandColorVariant[];
};

type BrandColorVariant = {
  name: string;
  hex: string;              // normalized to uppercase #RRGGBB
  usage_hint?: string;
  source?: "manual" | "ai_suggested" | "seed_migration" | "shopify_discovery" | "gemini" | string;
};
```

Example:

```json
{
  "palette": [
    { "name": "Forest", "hex": "#1F4D2E" },
    { "name": "Avocado", "hex": "#7CB342" },
    { "name": "Coral pop", "hex": "#FF6B5C" }
  ],
  "color_system": {
    "primary": {
      "key": "primary",
      "label": "Primary",
      "hex": "#1F4D2E",
      "usage_hint": "Main brand color for dominant identity moments, headline emphasis, and major visual anchors.",
      "agent_hint": "Prefer for main brand identity, key text/visual anchors, and high-recognition surfaces.",
      "variants": [
        { "name": "Forest", "hex": "#1F4D2E", "usage_hint": "Dark text and identity anchor", "source": "seed_migration" }
      ]
    },
    "secondary": {
      "key": "secondary",
      "label": "Secondary",
      "hex": "#7CB342",
      "usage_hint": "Support color for backgrounds, secondary surfaces, and balance around the primary color.",
      "agent_hint": "Use for background fields, supporting surfaces, and composition balance.",
      "variants": []
    },
    "tertiary": {
      "key": "tertiary",
      "label": "Tertiary / Accent",
      "hex": "#FF6B5C",
      "usage_hint": "Accent color for CTA, highlights, badges, and small high-attention elements.",
      "agent_hint": "Use sparingly for CTA, promotional badges, urgency marks, and highlights.",
      "variants": []
    }
  }
}
```

## Role semantics

The roles replace implicit interpretation of `palette[0]`, `palette[1]`, and `palette[2]`.

- `primary`: main brand identity color. Use for dominant identity moments, headline emphasis, key text/visual anchors, and high-recognition surfaces.
- `secondary`: support color. Use for backgrounds, secondary surfaces, and composition balance around the primary color.
- `tertiary`: accent color. Use sparingly for CTA, highlights, badges, urgency marks, and other small high-attention elements.

User-facing UI should label the third role as `Tertiary / Accent` in English and `Terciario / Acento` in Spanish/localized copy. The persisted role key remains `tertiary`.

`usage_hint` is editable user/product guidance. `agent_hint` is editable guidance for concept, prompt, rendering, and Liquid decisions. Both are brand context, not ad copy.

## Accepted variants

Each role can have accepted variants that define the brand-approved range for that role. Variants may be lighter, darker, warmer, cooler, or usage-specific alternatives.

Required fields:

- `name`
- `hex`

Optional fields:

- `usage_hint`: practical use such as `CTA hover`, `soft background`, `badge accent`, or `dark text`.
- `source`: provenance. Current expected values are `manual`, `ai_suggested`, `seed_migration`, `shopify_discovery` (discovered store color accepted into a role), and `gemini` (variant inside a backend recommendation draft); clients should tolerate unknown future strings.

Generation should treat variants as active approved colors, not as passive notes. When a role has variants, agents/renderers should choose from the base role color and accepted variants before inventing any non-brand color. If contrast or placement requirements cannot be satisfied from approved colors, that is a carry-over compliance gap rather than a reason to silently create arbitrary colors.

## Legacy palette compatibility and migration behavior

`palette` remains part of the public `BrandContext` contract for backward compatibility.

Compatibility rules:

- Existing palette-only brands remain valid.
- If `color_system` is missing, `BrandContext` normalizes it from `palette`:
  - `primary` = `palette[0]`
  - `secondary` = `palette[1]` if present, otherwise primary
  - `tertiary` = `palette[2]` if present, otherwise secondary
- Hex values normalize to uppercase `#RRGGBB` for palette colors, role colors, and variants.
- New saves should preserve `color_system` and keep `palette` available so old clients and fallback code continue to work during migration.
- Markdown seeds/frontmatter can contain `color_system`; import/export round-trips it.

The migration does not remove legacy palette semantics. It makes role semantics first-class and keeps palette as a compatibility layer.

## Supabase storage

Supabase stores color roles in a first-class column:

```sql
alter table public.brand_contexts add column if not exists color_system jsonb;

create index if not exists brand_contexts_color_system_gin_idx
    on public.brand_contexts using gin (color_system);
```

`brand_contexts.color_system` is canonical storage going forward. The brand service reads this top-level column first. It can still read legacy `source_metadata.color_system` when present, but new writes should store role data in `brand_contexts.color_system`, not buried in `source_metadata`.

## Palette suggestion API

Two routes exist:

```text
POST /brands/{brand_id}/palette-suggestions
POST /api/v1/brands/{brand_id}/palette-suggestions
```

Use `/api/v1` for new integrations. The root route is prototype compatibility.

Request body:

```ts
type PaletteSuggestionRouteRequest = {
  role_key: "primary" | "secondary" | "tertiary";
  base_hex?: string | null;          // defaults to selected role hex
  count?: number;                    // default 8, min 3, max 12
  intent?: string;                   // optional user/design intent
  draft_brand_context?: BrandContext | null;
};
```

`draft_brand_context` lets the frontend request suggestions for unsaved edits without persisting them. If omitted, the backend uses the saved brand for `brand_id`.

Response body:

```ts
type PaletteSuggestionResponse = {
  role_key: "primary" | "secondary" | "tertiary" | string;
  base_hex: string;
  source: "gemini";
  suggestions: Array<{
    name: string;
    hex: string;
    usage_hint: string;
    rationale?: string;
  }>;
};
```

Errors:

- `404`: brand id not found.
- `422`: invalid request shape, invalid role key, invalid hex, or invalid draft brand context.
- `503`: Gemini unavailable, Gemini call failed, response could not be parsed, or Gemini returned no valid suggestions.
- `/api/v1` also requires the normal demo auth/team context and returns `401` when auth is missing or malformed.

## Gemini requirement and no fake fallback

The user-facing/demo suggestion path is Gemini-only. The API response source is always `gemini`. When Gemini, API key, budget, or provider response quality is unavailable, the backend must return a clear `503` instead of deterministic or fake "AI" suggestions.

Deterministic color math may exist only as a private unit-test helper or explicitly labeled developer fixture. It must not be exposed as user-facing AI suggestions.

## Discovery recommendations and the color role system

Shopify brand discovery (full contract: `docs/architecture/brand-discovery-and-font-system.md`) feeds this color system through a second, evidence-backed AI flow:

- `POST /brands/{brand_id}/discovery-runs/{run_id}/recommendations` returns a Gemini draft of `BrandColorRecommendation` items, one per role (`role_key`, `base_hex`, `label`, hints, `variants`, `rationale`, `evidence_refs`). It is Gemini-only (`503` when unavailable) like palette suggestions; roles Gemini does not answer are backfilled from the user's approved system with `rationale: "kept from existing approved brand context"`.
- Accepting a recommendation replaces the whole role (label, base hex, hints, and variants), unlike per-role palette suggestions, which only append variants. Unaccepted roles keep their current values and variants. When at least one role is accepted, legacy `palette[0..2]` is re-synced to the role colors (extras beyond index 2 preserved) by both the frontend draft flow and the backend `apply-discovery-recommendations` merge.
- Variant provenance: variants inside a backend recommendation draft carry `source: "gemini"`. The frontend relabels accepted recommendation variants as `source: "ai_suggested"`, marks a discovered store color added to a role as `source: "shopify_discovery"`, and keeps `source: "manual"` for hand-entered variants.
- Draft-only rule is unchanged: discovery evidence and recommendation drafts never auto-apply. The UI accumulates accepted items into the local draft and persists through the normal Save/Guardar flow (`PUT /brands/{brand_id}`); API consumers can use `POST /brands/{brand_id}/apply-discovery-recommendations` for the same merge.

## Frontend usage rules

Brand editor behavior:

- Render role cards for Primary, Secondary, and Tertiary / Accent.
- Let users edit base role color, `usage_hint`, `agent_hint`, and role variants.
- Use `AI Palette Suggestions` per role.
- Send current draft brand state as `draft_brand_context` so suggestions reflect unsaved edits.
- Display suggestions in a draft/review tray.
- Accepting a suggestion appends it to `draft.color_system[role].variants` with `source: "ai_suggested"`.
- Accepted suggestions do not auto-save; existing Save/Guardar persists the full brand context.
- Dirty-state detection should include accepted suggestions and role/variant edits.
- Offline fallback seed brands remain viewable/editable where possible, but AI suggestions must show a backend/Gemini unavailable error and must not be generated locally as fake AI.

Frontend preview and local rendering should prefer `color_system` roles over flat `palette`, with legacy fallback for older data.

## Generation usage rules

Generation code should prefer explicit roles whenever `color_system` exists:

- Concept drafting uses primary as the main identity/text anchor, secondary as support/background, and tertiary as CTA/accent.
- Image prompts include role labels, base hexes, usage hints, agent hints, and accepted variants.
- HTML preview resolves CSS colors from roles first, then falls back to legacy palette order.
- Liquid payload/config carries the full `color_system` so Shopify-side/debug consumers can see role data.
- Accepted variants are eligible for active generation choices in concept, image, HTML, and Liquid output.
- Legacy palette-only brands must continue to generate through normalized role defaults and/or palette fallback.

## Known carry-over gaps

The current feature establishes the contract and first implementation, but does not complete every brand-governance capability:

- Full brand compliance audit gate for output colors, copy phrases, image directives, and role usage.
- Richer contrast-aware automatic selection among base colors and variants.
- Logo usage integration in generation and compliance checks.
- Rich brandbook/Figma import that extracts roles, variants, tone, logo rules, and usage constraints.
