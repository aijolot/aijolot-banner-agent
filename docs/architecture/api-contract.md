# API contract: prototype compatibility and `/api/v1`

The backend exposes two API namespaces:

1. Root-level prototype compatibility routes. These remain for older/static prototype entry points and local development compatibility.
2. Canonical integration routes under `/api/v1`. New integration work should use these routes.

## Auth and tenancy

Canonical `/api/v1` callers should send a demo/auth request context. Most implemented v1 routes fail closed with 401 when it is missing. Approval/comment/refinement routes can currently return service-unavailable before auth when their backing approval service is unavailable; callers should still send the same auth context. The MVP accepts either explicit demo headers or a bearer demo token:

```text
X-Aijolot-User-Id: <demo user id; UUID recommended for seeded fixtures>
X-Aijolot-Team-Id: <demo team id; UUID recommended for seeded fixtures>
X-Aijolot-Store-Id: <demo store id, optional on some routes>
Authorization demo bearer format: Bearer demo:<user_id>:<team_id>[:<store_id>]
```
Never put real provider secrets in these headers. They are only request identity/team context for the MVP. Missing or malformed auth returns 401 on protected `/api/v1` routes. Request team context scopes Supabase-backed services and no-Supabase fallback repositories.

Demo fixture values used by smoke/demo docs:

```text
team  = 00000000-0000-0000-0000-000000000001
user  = 00000000-0000-0000-0000-000000000601
store = 00000000-0000-0000-0000-000000000101
```

Root compatibility routes are unauthenticated prototype compatibility routes. They do not have the same auth contract and should not be used for new integration work.

## Health and API docs

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| GET | `/health` | No | Service health check. Returns `{ "status": "ok" }`. |
| GET | `/docs` | No | FastAPI OpenAPI UI when the backend is running locally. |

No `/api/v1/health` route is part of the current contract.

## Root prototype compatibility routes

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/brands` | List brand summaries through compatibility service. |
| POST | `/brands/import` | Import supported Markdown-backed brand context. |
| GET | `/brands/{brand_id}` | Get a brand context. |
| PUT | `/brands/{brand_id}` | Save a brand context. |
| POST | `/brands/{brand_id}/palette-suggestions` | Gemini-backed AI suggestions for accepted color variants for a selected color role. Returns 503 when Gemini is unavailable; no fake fallback suggestions. |
| POST | `/campaigns` | Create a campaign. |
| GET | `/campaigns` | List campaigns. |
| POST | `/campaigns/intake` | SSE campaign intake stream. |
| GET | `/campaigns/{campaign_id}` | Get campaign. |
| PATCH | `/campaigns/{campaign_id}` | Patch campaign/brief fields. |

Compatibility routes are retained but `/api/v1` is canonical.

## Canonical `/api/v1` routes

Most routes below require demo/auth context unless otherwise noted. Approval/comment/refinement routes should be called with auth too, but can currently return 503 service-unavailable before auth when the approval service is unavailable.

### Brands

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/v1/brands` | List brand summaries. Supabase-first; Markdown/demo fallback when Supabase is not configured. |
| POST | `/api/v1/brands/import` | Import Markdown-supported brand context. PDF/Figma extraction is partial/mock only and not in the deterministic smoke path. |
| GET | `/api/v1/brands/{brand_id}` | Return full brand context. |
| PUT | `/api/v1/brands/{brand_id}` | Validate and persist brand context. |
| POST | `/api/v1/brands/{brand_id}/palette-suggestions` | Return Gemini-backed draft palette suggestions for a selected brand color role. Requires auth and returns 503 when Gemini is unavailable. |

Seeded/fallback brand ids include `avocado_store`, `demo_apparel`, and `maison`.

#### Brand color system

`BrandContext` keeps the legacy flat `palette` and now also supports explicit `color_system` roles. The role contract is documented in detail in `docs/architecture/brand-context-color-system.md`.

Shape:

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

Role semantics:

- `primary`: main brand identity, key text/visual anchors, headline emphasis, and high-recognition surfaces.
- `secondary`: support color for backgrounds, secondary surfaces, and balance around primary.
- `tertiary`: accent color for CTA, highlights, badges, urgency marks, and small high-attention elements. UI copy should label this as `Tertiary / Accent` in English and `Terciario / Acento` in Spanish/localized copy; the persisted key remains `tertiary`.

`usage_hint` is user-facing guidance. `agent_hint` is generation guidance. Role `variants` are accepted colors for that role and include `name`, `hex`, optional `usage_hint`, and optional `source` such as `manual`, `ai_suggested`, or `seed_migration`. Generation should treat accepted variants as active approved choices for concept, image prompts, HTML, and Liquid rather than passive notes.

Legacy compatibility and persistence:

- Existing palette-only payloads remain valid.
- When `color_system` is missing, the backend normalizes from legacy palette order: primary = `palette[0]`, secondary = `palette[1]` when present otherwise primary, tertiary = `palette[2]` when present otherwise secondary.
- Hex values normalize to uppercase `#RRGGBB`.
- Supabase stores the canonical color system in the first-class `brand_contexts.color_system jsonb` column with a GIN index. The service reads that top-level column first and can read legacy `source_metadata.color_system`; new writes use the top-level column.
- Markdown/frontmatter seeds can contain `color_system` and round-trip through import/export.

#### Palette suggestions

Routes:

```text
POST /brands/{brand_id}/palette-suggestions
POST /api/v1/brands/{brand_id}/palette-suggestions
```

Root route is prototype compatibility. `/api/v1` is canonical and requires the same demo auth/team context as other v1 brand routes.

Request:

```json
{
  "role_key": "primary",
  "base_hex": "#1F4D2E",
  "count": 8,
  "intent": "More CTA-safe dark green variants",
  "draft_brand_context": { "...": "optional full BrandContext for unsaved UI edits" }
}
```

Fields:

- `role_key`: required, one of `primary`, `secondary`, `tertiary`.
- `base_hex`: optional; defaults to the selected role's current base hex.
- `count`: optional; default 8, min 3, max 12.
- `intent`: optional free text to guide Gemini.
- `draft_brand_context`: optional full `BrandContext`; used for suggestions without saving unsaved frontend changes.

Response:

```json
{
  "role_key": "primary",
  "base_hex": "#1F4D2E",
  "source": "gemini",
  "suggestions": [
    {
      "name": "Deep Grove",
      "hex": "#163B24",
      "usage_hint": "Darker primary for text or high-contrast hero overlays",
      "rationale": "Keeps the avocado identity while improving contrast."
    }
  ]
}
```

Gemini is required for user-facing/demo suggestions. The backend must not return deterministic or fake AI suggestions. If Gemini/config/budget/provider quality is unavailable, the route returns `503` with a clear detail. Other expected errors: `404` for missing brand, `422` for invalid input, and `401` for missing/malformed auth on `/api/v1`.

Frontend rules: suggestions are draft-only. Accepting a suggestion appends it to the selected role's variants with `source: "ai_suggested"`; nothing is persisted until the user uses the normal Save/Guardar flow. Offline fallback may show/edit seeded brands, but AI suggestions should be disabled or surface backend/Gemini unavailable rather than locally faking suggestions.

### Campaigns and intake

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/v1/campaigns` | Create campaign. |
| GET | `/api/v1/campaigns` | List campaigns scoped to request team. |
| POST | `/api/v1/campaigns/intake` | SSE stream with `token` events and final `done` event containing campaign state. Deterministic fallback is default unless Gemini intake is explicitly enabled. |
| GET | `/api/v1/campaigns/{campaign_id}` | Get campaign. |
| PATCH | `/api/v1/campaigns/{campaign_id}` | Patch campaign/structured brief fields. |

No-Supabase root/prototype fallback can create non-UUID prototype ids; authenticated `/api/v1` no-Supabase fallback creates UUID campaign ids so stage APIs can use the intake-returned id during local frontend integration.

### Stores, resources, and placements

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/v1/stores` | List stores for request team. |
| GET | `/api/v1/stores/{store_id}` | Get store summary. |
| GET | `/api/v1/stores/{store_id}/shopify/resources?resource_type=collection|product|page|search` | List seeded/cached Shopify resources. Live sync is non-MVP/manual. |
| GET | `/api/v1/stores/{store_id}/placement-types` | List seeded placement types. |
| GET | `/api/v1/stores/{store_id}/placement-types/{placement_type_key}/targets` | List valid target handles/slots. |
| POST | `/api/v1/placements/validate` | Validate placement payload. |
| POST | `/api/v1/campaigns/{campaign_id}/placement` | Save campaign placement. |
| GET | `/api/v1/campaigns/{campaign_id}/placement` | Get campaign placement. |

Seeded placement keys: `announcement_bar`, `hero_main`, `promo_card`, `collection_header`, `pdp_strip`, `pdp_cross_sell`, `footer_cta`, `search_results_banner`. Publishing rejects unsupported search-result placement with a clear error.

### Catalog, art direction, generation, previews, and audit

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/v1/campaigns/{campaign_id}/catalog-snapshot` | Freeze selected cached/seeded catalog context. |
| GET | `/api/v1/campaigns/{campaign_id}/catalog-snapshot` | Retrieve catalog snapshot. |
| PUT | `/api/v1/campaigns/{campaign_id}/art-direction` | Save art direction. Custom persona/model data is metadata-only/non-MVP. |
| GET | `/api/v1/campaigns/{campaign_id}/art-direction` | Retrieve art direction. |
| POST | `/api/v1/campaigns/{campaign_id}/generation-runs` | Start deterministic/provider-backed generation run. |
| GET | `/api/v1/campaigns/{campaign_id}/generation-runs/latest` | Latest run for campaign. |
| GET | `/api/v1/generation-runs/{run_id}` | Generation run detail. |
| GET | `/api/v1/generation-runs/{run_id}/events` | Ordered generation events mapped to five frontend steps. |
| GET | `/api/v1/campaigns/{campaign_id}/preview` | Rendered HTML preview with restrictive CSP. |
| GET | `/api/v1/campaigns/{campaign_id}/audit-report` | Audit report. Lighthouse is mock/manual unless manually run; AVIF may be labeled skipped. |

The deterministic smoke path does not call Gemini, Shopify, Supabase, Lighthouse, or external networks.

### Approval, revision, scheduling, and publishing

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/api/v1/campaigns/{campaign_id}/approval/request` | Create approval thread. |
| GET | `/api/v1/campaigns/{campaign_id}/approval` | Get approval state. |
| POST | `/api/v1/approval-threads/{thread_id}/comments` | Create pinned/general comment. |
| PATCH | `/api/v1/comments/{comment_id}/resolve` | Resolve comment. |
| POST | `/api/v1/approval-threads/{thread_id}/approve` | Approve as reviewer. All assigned reviewers must approve. |
| POST | `/api/v1/approval-threads/{thread_id}/request-changes` | Request changes and close/update approval state. |
| POST | `/api/v1/campaigns/{campaign_id}/refinement-requests` | Queue refinement request. |
| POST | `/api/v1/campaigns/{campaign_id}/variants/{variant_id}/select` | Select revision/variant. |
| POST | `/api/v1/campaigns/{campaign_id}/regenerate` | Create a new revision/generation run; does not mutate prior final assets. |
| GET | `/api/v1/campaigns/{campaign_id}/revisions` | List revisions. |
| POST | `/api/v1/campaigns/{campaign_id}/schedule` | Create schedule for approved/scheduled campaign. |
| PATCH | `/api/v1/campaigns/{campaign_id}/schedule` | Update schedule. |
| POST | `/api/v1/campaigns/{campaign_id}/schedule/cancel` | Cancel schedule. |
| POST | `/api/v1/campaigns/{campaign_id}/publish` | Publish controlled Liquid assets/metafield config to Shopify when real credentials and eligible state are present. Fail-closed otherwise. |
| POST | `/api/v1/campaigns/{campaign_id}/unpublish` | Remove only the campaign config from the controlled Shopify metafield. |

Scheduling is theme/date-config enforced for MVP; no active pg_cron due-publish job is required for the documented demo path. Approval/comment/refinement endpoints are documented for the contract surface but currently depend on approval service availability and may return 503 before auth in local fallback mode.

### Performance and evolutionary memory

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/v1/campaigns/{campaign_id}/performance` | Return snapshots/insights/proposals with explicit provenance. |
| POST | `/api/v1/campaigns/{campaign_id}/performance/snapshots` | Record manual/mock/seed/agent/live-labeled snapshot. |
| POST | `/api/v1/campaigns/{campaign_id}/optimization-proposals` | Create optimization proposal. |

Performance metrics in the MVP are manual/mock/seed/agent unless `live_analytics=true` and live ingestion is deliberately wired. Do not present demo performance data as live Shopify analytics.

## Provider and demo limitations

- Gemini/image providers are opt-in for most generation paths; brand palette suggestions are Gemini-only for the user-facing/demo path and return 503 when Gemini is unavailable instead of fake suggestions.
- Live Shopify resource sync/analytics ingestion is outside MVP/manual only.
- PDF/Figma extraction, custom persona/model support, full Lighthouse automation, generated A/B/C model exploration, full brand compliance auditing, richer contrast-aware color selection, and logo-usage integration are constrained/labeled in `docs/demo-script.md` or documented as carry-over gaps.
- Real Shopify publishing requires configured credentials and a safe target store/theme; never document or print real tokens.
