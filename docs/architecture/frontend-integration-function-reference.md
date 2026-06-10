# Frontend integration function reference

Purpose: give the frontend team and their agents a copy/paste-friendly map of the backend functions/endpoints created for the MVP, including parameters, request bodies, and functionality.

Source of truth checked on `main` after merge. Canonical frontend integration should use `/api/v1`. Root routes remain only for prototype compatibility.

## 0. Shared client setup

Recommended frontend base URL:

```ts
const API_ORIGIN = process.env.NEXT_PUBLIC_API_ORIGIN ?? "http://localhost:8000";
const API_BASE = `${API_ORIGIN}/api/v1`;
```

Do not set `NEXT_PUBLIC_API_BASE_URL` to `http://localhost:8000/api/v1` and then append `/api/v1` again.

Required demo auth context for most `/api/v1` calls:

```ts
export const demoAuthHeaders = {
  "X-Aijolot-User-Id": "00000000-0000-0000-0000-000000000601",
  "X-Aijolot-Team-Id": "00000000-0000-0000-0000-000000000001",
  "X-Aijolot-Store-Id": "00000000-0000-0000-0000-000000000101",
};
```

Alternative bearer format, if preferred:

```text
Authorization header value format: Bearer demo:user-id:team-id[:store-id]
```

Never put Gemini, Shopify, Supabase service-role, or any real provider secret in frontend headers.

Suggested client helper:

```ts
type Json = Record<string, unknown> | unknown[] | null;

function apiPath(path: string): string {
  return path.startsWith("/") ? path : `/${path}`;
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${apiPath(path)}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...demoAuthHeaders,
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${detail}`);
  }

  return response.json() as Promise<T>;
}

const get = <T>(path: string) => api<T>(path);
const post = <T>(path: string, body?: Json) => api<T>(path, { method: "POST", body: body == null ? undefined : JSON.stringify(body) });
const put = <T>(path: string, body: Json) => api<T>(path, { method: "PUT", body: JSON.stringify(body) });
const patch = <T>(path: string, body?: Json) => api<T>(path, { method: "PATCH", body: body == null ? undefined : JSON.stringify(body) });
```

Important caveats:

- Most `/api/v1` routes return `401` without demo auth context.
- Approval/comment/refinement routes should still send auth, but can currently return `503` before auth if the approval service is unavailable in local fallback mode.
- Some stage APIs require UUID campaign IDs. Campaigns created through `/api/v1/campaigns` or Supabase-backed intake are safest for full frontend integration.
- Performance values are manual/mock/seed/agent unless explicitly marked live; do not label demo values as live analytics.
- Publishing fails closed unless Shopify credentials and safe campaign state are configured.
- DELETE operations are not part of the MVP API surface. If the UI needs removal, hide/archive locally or ask backend for an explicit endpoint instead of assuming `DELETE` exists.

## 1. Health

### `getHealth()`

```ts
GET /health
```

Auth: none.

Functionality: checks FastAPI backend availability.

Response shape:

```ts
{ status: "ok" }
```

## 2. Brands

### `listBrands()`

```ts
GET /api/v1/brands
```

Auth: demo auth headers.

Functionality: lists brand summaries. Supabase-first; Markdown/demo fallback when Supabase is not configured.

Response: `BrandSummary[]`.

### `getBrand(brandId)`

```ts
GET /api/v1/brands/{brand_id}
```

Params:

- `brand_id: string` path param. Seeded/fallback ids include `avocado_store`, `demo_apparel`, `maison`.

Functionality: loads full brand context for Brand Context UI.

Response: `BrandContext`.

### `saveBrand(brandId, brand)`

```ts
PUT /api/v1/brands/{brand_id}
```

Params:

- `brand_id: string` path param.
- Body: `BrandContext`.

Functionality: validates and saves brand context. `color_system` roles are persisted with the brand; keep legacy `palette` populated for compatibility. See `docs/architecture/brand-context-color-system.md` for role semantics and generation rules.

Body fields:

```ts
type PaletteColor = { name: string; hex: string };

type BrandColorVariant = {
  name: string;
  hex: string;
  usage_hint?: string;
  source?: "manual" | "ai_suggested" | "seed_migration" | string;
};

type BrandColorRole = {
  key: "primary" | "secondary" | "tertiary";
  label: string;
  hex: string;
  usage_hint?: string;
  agent_hint?: string;
  variants?: BrandColorVariant[];
};

type BrandContext = {
  id: string;
  name: string;
  palette: PaletteColor[]; // legacy compatibility remains required
  color_system?: {
    primary: BrandColorRole;
    secondary: BrandColorRole;
    tertiary: BrandColorRole;
  } | null;
  typography?: object;
  voice?: object;
  logo_url?: string | null;
  image_style_directives?: string[];
  shopify: object;
  notes?: string;
};
```

### `suggestBrandPalette(brandId, input)`

```ts
POST /api/v1/brands/{brand_id}/palette-suggestions
```

Params:

- `brand_id: string` path param.
- Body: `PaletteSuggestionRouteRequest`.

Functionality: asks Gemini for draft accepted-variant suggestions for one brand color role. Use this for the `AI Palette Suggestions` button. Send the current unsaved brand draft as `draft_brand_context` so suggestions reflect local role/color edits. The route does not save suggestions.

Body:

```ts
type PaletteSuggestionRouteRequest = {
  role_key: "primary" | "secondary" | "tertiary";
  base_hex?: string | null;
  count?: number; // default 8, min 3, max 12
  intent?: string;
  draft_brand_context?: BrandContext | null;
};
```

Response:

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

Frontend rules: show suggestions as draft choices; accepting one appends it to `draft.color_system[role].variants` with `source: "ai_suggested"`; persist only through the normal `saveBrand()` flow. If the backend/network/Gemini is unavailable, surface the error and do not create local deterministic "AI" suggestions. Expected errors include `401` without auth, `404` for missing brand, `422` for invalid input, and `503` when Gemini is unavailable or returns no usable suggestions.

### `importBrand(input)`

```ts
POST /api/v1/brands/import
```

Body:

```ts
type BrandImportRequest = {
  brand_id?: string | null;
  path?: string | null;
};
```

Functionality: imports supported Markdown-backed brand context. PDF/Figma extraction is not part of the deterministic demo path.

Response: `BrandContext`.

## 3. Campaigns and intake

### `createCampaign(input?)`

```ts
POST /api/v1/campaigns
```

Body optional:

```ts
type CampaignCreate = {
  title?: string | null;
  raw_brief?: string | null;
};
```

Functionality: creates a backend campaign. Use this when the frontend needs a UUID campaign before saving placement/art/generation.

Response: `Campaign`.

### `listCampaigns()`

```ts
GET /api/v1/campaigns
```

Functionality: lists campaigns scoped to request team.

Response: `Campaign[]`.

### `getCampaign(campaignId)`

```ts
GET /api/v1/campaigns/{campaign_id}
```

Params:

- `campaign_id: string` path param.

Functionality: loads one campaign.

Response: `Campaign`.

### `patchCampaign(campaignId, patch)`

```ts
PATCH /api/v1/campaigns/{campaign_id}
```

Params:

- `campaign_id: string` path param.
- Body: `BriefPatch`.

Functionality: persists editable campaign/brief chips.

Body fields:

```ts
type BriefPatch = {
  title?: string | null;
  goal?: string | null;
  audience?: string | null;
  cta?: string | null;
  tone?: string | null;
  urgency?: string | null;
  placement?: string | null;
  deadline?: string | null;
};
```

Response: `Campaign`.

### `streamIntake(message, campaignId?)`

```ts
POST /api/v1/campaigns/intake
```

Params/body:

```ts
type IntakeRequest = {
  message: string;
  campaign_id?: string | null;
};
```

Functionality: streams campaign intake progress as Server-Sent Event-like `data:` chunks. The frontend should parse `token` events for text and the final `done` event for the campaign.

Headers:

```ts
{
  ...demoAuthHeaders,
  "Content-Type": "application/json"
}
```

Response text contains chunks like:

```text
data: {"type":"token","text":"..."}

data: {"type":"done","campaign":{...},"complete":true,"missing":[]}
```

Recommended incremental parser:

```ts
type IntakeEvent =
  | { type: "token"; text: string }
  | { type: "done"; campaign: Campaign; complete: boolean; missing: string[] };

async function streamIntakeEvents(
  message: string,
  onEvent: (event: IntakeEvent) => void,
  campaignId?: string | null,
) {
  const response = await fetch(`${API_BASE}/campaigns/intake`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      ...demoAuthHeaders,
    },
    body: JSON.stringify({ message, campaign_id: campaignId ?? null }),
  });
  if (!response.ok || !response.body) {
    throw new Error(`intake failed: ${response.status} ${await response.text()}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const chunk = buffer.slice(0, boundary).trim();
      buffer = buffer.slice(boundary + 2);
      if (chunk.startsWith("data: ")) onEvent(JSON.parse(chunk.slice(6)) as IntakeEvent);
      boundary = buffer.indexOf("\n\n");
    }

    if (done) break;
  }
}
```

For tests or non-streaming environments, consuming `await response.text()` and splitting on blank lines is acceptable, but browser chat UX should prefer the `ReadableStream` pattern above.

Core `Campaign` shape:

```ts
type Campaign = {
  id: string;
  title: string;
  raw_brief: string;
  structured_brief: {
    goal?: string | null;
    audience?: string | null;
    cta?: string | null;
    tone?: string | null;
    urgency?: string | null;
    placement?: string | null;
    deadline?: string | null;
  };
  status: string;
  messages: Array<object>;
};
```

## 4. Stores, Shopify resources, and placement

### `listStores()`

```ts
GET /api/v1/stores
```

Functionality: lists stores available to request team.

Response: `StoreSummary[]`.

### `getStore(storeId)`

```ts
GET /api/v1/stores/{store_id}
```

Params:

- `store_id: string` path param. Demo store: `00000000-0000-0000-0000-000000000101`.

Response: `StoreSummary`.

### `listShopifyResources(storeId, resourceType)`

```ts
GET /api/v1/stores/{store_id}/shopify/resources?resource_type=collection|product|page|search
```

Params:

- `store_id: string` path param.
- `resource_type: "collection" | "product" | "page" | "search"` query param.

Functionality: returns seeded/cached Shopify resource options for selectors. This is not live Shopify sync unless explicitly wired.

Response: `ShopifyResource[]`.

### `listPlacementTypes(storeId)`

```ts
GET /api/v1/stores/{store_id}/placement-types
```

Functionality: returns supported placement types for the store.

Seeded placement keys:

```text
announcement_bar
hero_main
promo_card
collection_header
pdp_strip
pdp_cross_sell
footer_cta
search_results_banner
```

Response: `PlacementType[]`.

### `listPlacementTargets(storeId, placementTypeKey)`

```ts
GET /api/v1/stores/{store_id}/placement-types/{placement_type_key}/targets
```

Params:

- `store_id: string` path param.
- `placement_type_key: string` path param.

Functionality: returns valid target handles/slots for a placement type.

Response: `PlacementTargetMap`.

### `validatePlacement(input)`

```ts
POST /api/v1/placements/validate
```

Body: `PlacementValidateRequest`, same fields as `CampaignPlacementUpsert` below.

Functionality: validates target/mode/slot before saving campaign placement.

Response: `PlacementValidationResponse`.

### `saveCampaignPlacement(campaignId, placement)`

```ts
POST /api/v1/campaigns/{campaign_id}/placement
```

Params:

- `campaign_id: string` path param; UUID recommended/required for stage APIs.
- Body: `CampaignPlacementUpsert`.

Functionality: saves selected placement for a campaign.

Body fields:

```ts
type CampaignPlacementUpsert = {
  store_id: string;
  placement_type_key: string;
  mode: "existing_section" | "new_section";
  target_type: "home" | "collection" | "product" | "page" | "search" | "store";
  target_resource_gid?: string | null;
  target_handle?: string | null;
  target_title?: string | null;
  existing_placement_key?: string | null;
  existing_placement_label?: string | null;
  existing_placement_size?: string | null;
  slot?: string | null;
  slot_order?: number;
  scope_rule?: Record<string, unknown>;
  layout_json?: Record<string, unknown>;
};
```

Response: `CampaignPlacementResponse`.

### `getCampaignPlacement(campaignId)`

```ts
GET /api/v1/campaigns/{campaign_id}/placement
```

Functionality: loads saved campaign placement.

Response: `CampaignPlacementResponse`.

## 5. Catalog and art direction

### `createCatalogSnapshot(campaignId, input?)`

```ts
POST /api/v1/campaigns/{campaign_id}/catalog-snapshot
```

Body optional:

```ts
type CatalogSnapshotCreate = {
  store_id?: string | null;
  query_summary?: string | null;
  discount_rule?: Record<string, unknown>;
  resource_types?: string[];
  limit?: number;
};
```

Functionality: freezes selected cached/seeded catalog context for the campaign.

Response: `CatalogSnapshotResponse`.

### `getCatalogSnapshot(campaignId)`

```ts
GET /api/v1/campaigns/{campaign_id}/catalog-snapshot
```

Functionality: retrieves the frozen catalog snapshot.

Response: `CatalogSnapshotResponse`.

### `saveArtDirection(campaignId, input)`

```ts
PUT /api/v1/campaigns/{campaign_id}/art-direction
```

Body:

```ts
type ArtDirectionUpsert = {
  background_mode: "hero" | "usage";
  hero_style_key?: string | null;
  model_key?: string | null;
  custom_model?: Record<string, unknown>;
  fold_percentage?: number; // default 55
  layout_hints?: Record<string, unknown>;
};
```

Functionality: saves art direction before generation. Custom model/persona is metadata-only/non-MVP.

Response: `ArtDirectionResponse`.

### `getArtDirection(campaignId)`

```ts
GET /api/v1/campaigns/{campaign_id}/art-direction
```

Functionality: loads saved art direction.

Response: `ArtDirectionResponse`.

## 6. Generation, preview, audit, and revisions

### `startGenerationRun(campaignId, input?)`

```ts
POST /api/v1/campaigns/{campaign_id}/generation-runs
```

Body optional:

```ts
type GenerationRunCreate = {
  run_type?: "initial" | "refinement" | "v2_optimization";
  parent_run_id?: string | null;
  started_by?: string | null;
  metadata?: Record<string, unknown>;
};
```

Functionality: starts a deterministic/provider-backed generation run and creates frontend-visible progress state.

Response: `GenerationRunResponse`.

### `getLatestGenerationRun(campaignId)`

```ts
GET /api/v1/campaigns/{campaign_id}/generation-runs/latest
```

Functionality: returns latest generation run for the campaign.

Response: `GenerationRunResponse`.

### `getGenerationRun(runId)`

```ts
GET /api/v1/generation-runs/{run_id}
```

Functionality: returns one generation run.

Response: `GenerationRunResponse`.

### `listGenerationEvents(runId)`

```ts
GET /api/v1/generation-runs/{run_id}/events
```

Functionality: returns ordered progress events mapped to frontend steps.

Response: `GenerationEventResponse[]`.

Event shape:

```ts
type FrontendStep = "intake_context" | "concept" | "image" | "render_audit" | "review_publish";
type GenerationEventStatus = "started" | "succeeded" | "failed" | "retried" | "escalated";

type GenerationEventResponse = {
  id: string;
  generation_run_id: string;
  node_key: string;
  frontend_step: FrontendStep;
  status: GenerationEventStatus;
  input_summary?: Record<string, unknown> | null;
  output_summary?: Record<string, unknown> | null;
  duration_ms?: number | null;
  cost_usd?: number | null;
  created_at?: string | null;
};
```

Frontend progress mapping:

| `frontend_step` | UI label | ADK/node keys included |
| --- | --- | --- |
| `intake_context` | Intake & context | `load_brand_context`, `intake_campaign_idea`, `capture_user_personalization`, `research_best_practices` |
| `concept` | Banner concept | `draft_banner_concept` |
| `image` | Image & assets | `generate_image`, `optimize_assets` |
| `render_audit` | Render & audit | `render_html`, `audit` |
| `review_publish` | Review & publish | `human_review`, `schedule_or_publish`, `publish_to_shopify` |

Knowledge Graph / 2nd Brain note: KG retrieval is internal to the agent, not a direct frontend API. If the backend emits a `generation_events` row with `node_key: "research_best_practices"`, its `output_summary` is the frontend-safe place to show a small "Powered by best practices"/"Context used" callout. Treat `output_summary` keys as optional because deterministic fallback and provider-backed runs may include different detail levels.

### `getCampaignPreview(campaignId)`

```ts
GET /api/v1/campaigns/{campaign_id}/preview
```

Functionality: returns rendered HTML preview with restrictive CSP.

Response: `text/html`.

### `getCampaignAuditReport(campaignId)`

```ts
GET /api/v1/campaigns/{campaign_id}/audit-report
```

Functionality: returns audit report. Lighthouse is mock/manual unless run separately; AVIF can be labeled skipped.

Response: JSON object.

### `selectVariant(campaignId, variantId)`

```ts
POST /api/v1/campaigns/{campaign_id}/variants/{variant_id}/select
```

Functionality: selects the chosen generated revision/variant.

Response: `VariantSelectionResponse`.

### `regenerateCampaign(campaignId, input?)`

```ts
POST /api/v1/campaigns/{campaign_id}/regenerate
```

Body optional:

```ts
type RegenerateRequest = {
  prompt?: string | null;
  refinement_request_id?: string | null;
  source_revision_id?: string | null;
  requested_by?: string | null;
};
```

Functionality: creates a new revision/generation run without mutating prior final assets.

Response: `RegenerateResponse`.

### `listCampaignRevisions(campaignId)`

```ts
GET /api/v1/campaigns/{campaign_id}/revisions
```

Functionality: lists revision history for the campaign.

Response: `CampaignRevisionResponse[]`.

Revision / layout / audience variant model:

```ts
type CampaignRevisionResponse = {
  id: string;
  campaign_id: string;
  generation_run_id?: string | null;
  revision_number: number;
  status: "draft" | "selected" | "superseded" | "approved" | "published" | string;
  concept: Record<string, unknown>;
  liquid_config: Record<string, unknown>;
  html_preview?: string | null;
  preview_storage_path?: string | null;
  created_at?: string | null;
  layout_variants: LayoutVariantResponse[];
  variants: RevisionVariantResponse[];
};

type LayoutVariantResponse = {
  id: string;
  revision_id: string;
  key: string; // deterministic MVP keys: "A" | "B" | "C"
  name: string;
  description?: string | null;
  layout_type?: string | null;
  is_recommended: boolean;
  config: Record<string, unknown>;
};

type RevisionVariantResponse = {
  id: string;
  revision_id: string;
  segment_key: string; // e.g. default, vip, new_signup, masculino, femenino when available
  segment_label: string;
  customer_tag?: string | null;
  audience_rule: Record<string, unknown>;
  product_snapshot_item_id?: string | null;
  eyebrow?: string | null;
  headline?: string | null;
  subheadline?: string | null;
  cta_text?: string | null;
  cta_url?: string | null;
  palette: Record<string, unknown>;
};
```

Navigation rule: there are no direct MVP endpoints like `GET /api/v1/revisions/{id}/variants` or `GET /api/v1/variants/{id}/assets`. Use `listCampaignRevisions(campaignId)` to obtain revision-level `layout_variants` and audience `variants`, and use `getCampaignPreview(campaignId)` when you need composed HTML. Asset rows exist in the database hierarchy (`campaign_revisions -> banner_layout_variants / banner_variants -> banner_assets`), but direct asset navigation is intentionally encapsulated by preview/render endpoints for the MVP.

## 7. Approval, comments, and refinement

Current caveat: these endpoints should be called with demo auth, but local fallback can return `503` before auth when approval service is unavailable. Frontend should display this as a backend/service unavailable state, not as successful approval.

### `requestApproval(campaignId, input?)`

```ts
POST /api/v1/campaigns/{campaign_id}/approval/request
```

Body:

```ts
type ApprovalRequestCreate = {
  revision_id?: string | null;
  requested_by?: string | null;
  approval_policy?: string; // default all_members
  reviewers?: string[];
};
```

Functionality: creates/requests approval for a campaign revision.

Response: `ApprovalThreadResponse`.

### `getCampaignApproval(campaignId)`

```ts
GET /api/v1/campaigns/{campaign_id}/approval
```

Functionality: gets current approval state.

Response: `ApprovalStateResponse`.

### `createComment(threadId, input)`

```ts
POST /api/v1/approval-threads/{thread_id}/comments
```

Body:

```ts
type CommentCreate = {
  author_id?: string | null;
  body: string;
  pin_x?: number | null; // 0..100
  pin_y?: number | null; // 0..100
  banner_variant_id?: string | null;
  layout_variant_key?: string | null;
  device_key?: "desktop" | "tablet" | "mobile" | null;
};
```

Functionality: creates general or pinned review comment.

Response: `CommentResponse`.

### `resolveComment(commentId, input?)`

```ts
PATCH /api/v1/comments/{comment_id}/resolve
```

Body optional: `CommentResolve`.

Functionality: marks a comment as resolved.

Response: `CommentResponse`.

### `approveThread(threadId, input)`

```ts
POST /api/v1/approval-threads/{thread_id}/approve
```

Body:

```ts
type ApprovalActionCreate = {
  user_id: string;
  note?: string | null;
};
```

Functionality: records reviewer approval. MVP policy requires all assigned reviewers to approve.

Response: `ApprovalThreadResponse`.

### `requestChanges(threadId, input)`

```ts
POST /api/v1/approval-threads/{thread_id}/request-changes
```

Body:

```ts
type ChangeRequestCreate = {
  user_id: string;
  note?: string | null;
  prompt?: string | null;
  addressed_comment_ids?: string[];
};
```

Functionality: requests changes and can seed a refinement prompt.

Response: `ApprovalThreadResponse`.

### `createRefinementRequest(campaignId, input)`

```ts
POST /api/v1/campaigns/{campaign_id}/refinement-requests
```

Body:

```ts
type RefinementRequestCreate = {
  source_revision_id?: string | null;
  requested_by?: string | null;
  prompt: string;
  addressed_comment_ids?: string[];
};
```

Functionality: queues a refinement request for later regeneration.

Response: `RefinementRequestResponse`.

## 8. Scheduling and publishing

### `scheduleCampaign(campaignId, input)`

```ts
POST /api/v1/campaigns/{campaign_id}/schedule
```

Body:

```ts
type ScheduleCreate = {
  revision_id?: string | null;
  starts_at: string; // ISO datetime
  ends_at?: string | null; // ISO datetime
  timezone?: string; // default UTC
  auto_unpublish?: boolean; // default true
  created_by?: string | null;
};
```

Functionality: schedules an approved campaign. Backend rejects invalid campaign state.

Response: `ScheduleResponse`.

### `updateSchedule(campaignId, input)`

```ts
PATCH /api/v1/campaigns/{campaign_id}/schedule
```

Body:

```ts
type ScheduleUpdate = {
  starts_at?: string | null;
  ends_at?: string | null;
  timezone?: string | null;
  auto_unpublish?: boolean | null;
};
```

Functionality: updates existing schedule.

Response: `ScheduleResponse`.

### `cancelSchedule(campaignId)`

```ts
POST /api/v1/campaigns/{campaign_id}/schedule/cancel
```

Functionality: cancels campaign schedule.

Response: `ScheduleResponse`.

### `publishCampaign(campaignId)`

```ts
POST /api/v1/campaigns/{campaign_id}/publish
```

Functionality: publishes controlled Liquid assets/metafield config to Shopify when real credentials and eligible campaign state are present. Fails closed otherwise.

Response: `PublishJobResponse`.

### `unpublishCampaign(campaignId)`

```ts
POST /api/v1/campaigns/{campaign_id}/unpublish
```

Functionality: removes only this campaign's config from the controlled Shopify metafield.

Response: `PublishJobResponse`.

## 9. Performance and evolutionary memory

### `getCampaignPerformance(campaignId)`

```ts
GET /api/v1/campaigns/{campaign_id}/performance
```

Functionality: returns performance snapshots, optimization insights, and optimization proposals with provenance labels.

Response: `CampaignPerformanceResponse`.

### `createPerformanceSnapshot(campaignId, input)`

```ts
POST /api/v1/campaigns/{campaign_id}/performance/snapshots
```

Body:

```ts
type PerformanceSnapshotCreate = {
  revision_id?: string | null;
  source?: "manual" | "mock" | "seed" | "agent";
  window_start?: string | null;
  window_end?: string | null;
  impressions?: number;
  clicks?: number;
  ctr?: number | null;
  conversions?: number;
  conversion_rate?: number | null;
  load_p75_ms?: number | null;
  weight_saved_pct?: number | null;
  segment_breakdown?: Array<Record<string, unknown>>;
  trend?: Record<string, unknown>;
};
```

Functionality: records manual/mock/seed/agent performance. Backend derives/bounds rates and rejects inconsistent counts.

Response: `PerformanceSnapshotResponse` with `live_analytics` and `data_source_label`.

### `createOptimizationProposal(campaignId, input)`

```ts
POST /api/v1/campaigns/{campaign_id}/optimization-proposals
```

Body:

```ts
type OptimizationProposalCreate = {
  source_revision_id: string;
  proposed_revision_id?: string | null;
  segment_key?: string | null;
  rationale: string;
  projected_lift?: Record<string, unknown>;
  status?: "draft" | "sent_to_approval" | "accepted" | "rejected";
};
```

Functionality: creates a V2 optimization proposal tied to the campaign/revision.

Response: `OptimizationProposalResponse`.

## 10. Explicit non-scope for MVP frontend agents

The following are intentionally not part of the MVP API surface:

- No `DELETE` endpoints. Do not assume delete exists for campaigns, comments, revisions, brands, schedules, or assets.
- No direct Knowledge Graph query endpoint. KG/2nd Brain retrieval is an internal generation event (`research_best_practices`) surfaced only through generation run outputs/events.
- No direct variant/asset navigation endpoints. Use `listCampaignRevisions`, `selectVariant`, `getCampaignPreview`, and `getCampaignAuditReport`.
- No live Shopify resource sync or live analytics ingestion endpoint in the deterministic demo path.

## 11. Root compatibility functions, avoid for new frontend work

These routes remain unauthenticated for older prototype compatibility only:

```text
GET  /brands
POST /brands/import
GET  /brands/{brand_id}
PUT  /brands/{brand_id}
POST /brands/{brand_id}/palette-suggestions
POST /campaigns
GET  /campaigns
POST /campaigns/intake
GET  /campaigns/{campaign_id}
PATCH /campaigns/{campaign_id}
```

Frontend agents should prefer `/api/v1` functions above.

## 12. Recommended frontend implementation order

1. Add shared API client with base URL and demo auth headers.
2. Wire `listBrands`, `getBrand`, `saveBrand`, and `suggestBrandPalette` for role-based color editing.
3. Wire `createCampaign` or `streamIntake`; store returned backend campaign id.
4. Wire `patchCampaign` for editable brief chips.
5. Wire placement selectors: stores/resources/placement-types/targets/validate/save.
6. Wire art direction save/load.
7. Wire generation start/latest/events and show progress.
8. Wire preview/audit display.
9. Wire approval/comment/refinement, with visible `503` service-unavailable handling.
10. Wire schedule/publish/unpublish, with fail-closed error handling.
11. Wire performance/proposals with non-live labels.

## 13. Quick smoke checklist for frontend agents

Before claiming connected frontend/backend:

- Backend is running at `http://localhost:8000`.
- Frontend API base does not double-prefix `/api/v1`.
- Every `/api/v1` request includes demo auth context.
- Intake returns a backend campaign object and the frontend stores its `id`.
- Stage APIs use a UUID campaign id.
- Backend errors are visible in UI; frontend does not silently mark schedule/publish/approval as successful.
- Performance and Lighthouse values are labeled mock/manual/non-live unless live ingestion is explicitly configured.
