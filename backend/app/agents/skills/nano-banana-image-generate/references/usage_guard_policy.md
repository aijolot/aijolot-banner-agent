# Usage Guard Policy

Rate limiting and cost control for image generation in the Nano Banana Image Generate skill.

## Soft rate limit

| Parameter | Value | Config key |
|-----------|-------|-----------|
| Limit | 20 generations | `SOFT_IMAGE_GENERATION_LIMIT_PER_15_MINUTES` |
| Window | 15 minutes | Hardcoded |
| Scope | Per user_id | Tracked in `generation_usage_events` table |
| Action | Warn (metadata flag) | `usage_guard.warning: true` |
| Behavior | **Soft** — does NOT block | Image still generated |

## Daily cost cap

| Parameter | Value | Config key |
|-----------|-------|-----------|
| Cap | $5.00 USD | `DAILY_COST_CAP_USD` |
| Scope | Global (all users) | Tracked via cost accumulation |
| Action | Warn | Logged, not blocked in MVP |
| Behavior | **Soft** in MVP | Post-MVP: hard block |

## Provider selection

| `IMAGE_GENERATION_PROVIDER` | Provider class | Image source |
|-----------------------------|---------------|-------------|
| `gemini` (explicit) | `GeminiImageProvider` | Gemini 3.1 Pro Image API |
| `""` / unset / other | `FakeImageProvider` | Deterministic minimal PNG |

## Usage event schema

Recorded per invocation in `generation_usage_events`:

```sql
user_id         -- nullable, for per-user tracking
team_id         -- nullable
campaign_id     -- nullable
event_type      -- "image_generation"
provider        -- "gemini" or "fake"
model           -- model identifier
estimated_cost  -- nullable decimal
metadata        -- JSONB: mime_type, size_bytes
created_at      -- timestamp
```

## Usage guard response metadata

Attached to every image generation response:

```json
{
  "count": 3,           // generations in current window
  "limit": 20,          // configured limit
  "window": "15min",    // window duration
  "warning": false      // true when count >= limit
}
```

## Decision rationale

Soft limits were chosen because:
1. Blocking mid-pipeline disrupts the user workflow
2. The HITL gate at node 10 provides a natural review point
3. Cost visibility is more important than hard blocks in MVP
4. Hard blocking is planned for post-MVP production hardening
