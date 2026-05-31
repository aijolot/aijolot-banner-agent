# API contract: prototype compatibility and `/api/v1`

This backend currently exposes two API namespaces:

1. Prototype compatibility routes at the root path. These are kept for the static frontend prototype and must not be removed until that frontend has migrated.
2. Canonical integration routes under `/api/v1`. New backend/frontend integration work should use these routes.

## Health

| Method | Path | Status | Notes |
| --- | --- | --- | --- |
| GET | `/health` | Active | Root-level service health check. Returns `{ "status": "ok" }`. |

No `/api/v1/health` route is introduced in this task; `/health` remains the health-check contract.

## Brands

| Method | Prototype path | Canonical path | Notes |
| --- | --- | --- | --- |
| GET | `/brands` | `/api/v1/brands` | List available brand summaries. |
| GET | `/brands/{brand_id}` | `/api/v1/brands/{brand_id}` | Return a full brand context, or 404 when missing. |
| PUT | `/brands/{brand_id}` | `/api/v1/brands/{brand_id}` | Validate and persist a brand context. |

## Campaign intake

| Method | Prototype path | Canonical path | Notes |
| --- | --- | --- | --- |
| POST | `/campaigns/intake` | `/api/v1/campaigns/intake` | Accepts an intake message and optional `campaign_id`. Streams Server-Sent Events with `token` events followed by one `done` event containing campaign state. |

## Campaign CRUD

| Method | Prototype path | Canonical path | Notes |
| --- | --- | --- | --- |
| GET | `/campaigns/{campaign_id}` | `/api/v1/campaigns/{campaign_id}` | Return a campaign, or 404 when missing. |
| PATCH | `/campaigns/{campaign_id}` | `/api/v1/campaigns/{campaign_id}` | Apply a partial structured-brief update, or 404 when missing. |

## Compatibility policy

Root-level prototype routes remain enabled for now. New callers should prefer `/api/v1` for stable integration paths. The `/api/v1` routes reuse the same endpoint logic as the prototype routes so validation, status codes, and response shapes stay aligned.
