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

Seeded/fallback brand ids include `avocado_store`, `demo_apparel`, and `maison`.

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

- Gemini/image providers are opt-in; deterministic/fake providers are safe defaults for tests and smoke.
- Live Shopify resource sync/analytics ingestion is outside MVP/manual only.
- PDF/Figma extraction, custom persona/model support, full Lighthouse automation, and generated A/B/C model exploration are constrained/labeled in `docs/demo-script.md`.
- Real Shopify publishing requires configured credentials and a safe target store/theme; never document or print real tokens.
