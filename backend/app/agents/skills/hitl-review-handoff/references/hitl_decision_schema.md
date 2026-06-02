# HITL Decision Schema

Contract for the human review decision at node 10 of the banner pipeline.

## HITLDecision model

```python
class HITLDecision(BaseModel):
    action: str          # "approve" | "reject" | "edit_request" | "schedule"
    target_publish_at: datetime | None = None  # only for action="schedule"
    reviewer: str        # reviewer user ID (UUID recommended)
    notes: str | None = None  # required for reject/edit_request
```

## Action semantics

| Action | Meaning | Downstream routing | Notes requirement |
|--------|---------|-------------------|-------------------|
| `approve` | Banner is approved for immediate publish | → node 11 → "immediate" → node 12 | Optional |
| `reject` | Banner rejected — needs re-draft | → node 5 (concept re-draft) | **Required** — what to fix |
| `edit_request` | Banner needs specific changes | → node 5 (re-draft with edit instructions) | **Required** — change details |
| `schedule` | Banner approved for scheduled publish | → node 11 → "scheduled" → node 12 at target time | Optional; `target_publish_at` required |

## Validation rules

| Field | Rule | Error on violation |
|-------|------|--------------------|
| `action` | Must be one of 4 allowed values | Reject callback |
| `reviewer` | Must be non-empty string | Reject callback |
| `notes` | Must be non-empty when `action` is `reject` or `edit_request` | Reject callback |
| `target_publish_at` | Must be future datetime when `action` is `schedule` | Reject callback |
| `target_publish_at` | Must be None when `action` is not `schedule` | Ignored (cleared) |

## SSE event format

### Review requested (pipeline → frontend)

```json
{
  "type": "hitl_review_required",
  "session_id": "uuid",
  "payload": {
    "audit_summary": {
      "status": "pass|warn|fail",
      "findings_count": {"fail": 0, "warn": 2},
      "root_cause_hint": "string or null"
    },
    "preview_html": "string (or URL)",
    "brand_summary": {
      "name": "Avocado Store",
      "palette_count": 3,
      "voice_tone": ["warm", "confident"]
    },
    "concept_summary": {
      "headline": "string",
      "subheadline": "string",
      "cta": "string",
      "layout": "string"
    },
    "variants": [
      {"customer_tag": "default", "intent_delta": "string"},
      {"customer_tag": "vip", "intent_delta": "string"}
    ],
    "asset_summary": {
      "total_weight_kb": 45.2,
      "breakpoints": [320, 768, 1280, 1920],
      "avif_available": true
    }
  }
}
```

### Review completed (frontend → pipeline)

```json
{
  "type": "hitl_review_completed",
  "session_id": "uuid",
  "decision": {
    "action": "approve",
    "reviewer": "00000000-0000-0000-0000-000000000601",
    "notes": null,
    "target_publish_at": null
  }
}
```

## Timeout policy

| Parameter | Value |
|-----------|-------|
| Timeout duration | 24 hours |
| Timeout action | Mark session "expired" |
| Auto-approve on timeout | **NO — never** |
| Notification | audit_log event `{event: "review_expired"}` |
| Recovery | Manual re-trigger of pipeline |

## Audit log events emitted

| Event | When | Payload |
|-------|------|---------|
| `review_requested` | Pipeline paused | `{session_id, audit_status, variant_count}` |
| `review_completed` | Decision received | `{session_id, action, reviewer}` |
| `review_expired` | 24h timeout | `{session_id, reason: "timeout"}` |
