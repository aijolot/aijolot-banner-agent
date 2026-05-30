---
name: schedule-or-publish-route
description: Branch on HITL decision — immediate publish OR INSERT into scheduled_banners.
metadata:
  type: deterministic
  owner_node: 11
  ticket: GH-18
  policy: write-action — HITL approve required upstream
---

## Inputs
- `hitl_decision: HITLDecision`
- `state: BannerSessionState`

## Outputs
- `route: "immediate" | "scheduled"`

## Acceptance criteria
- [ ] Raises if hitl_decision.action != "approve" and != "schedule"
- [ ] Scheduled path INSERTs row with payload jsonb + target_publish_at
- [ ] Immediate path returns "immediate" so Coordinator invokes node 12
