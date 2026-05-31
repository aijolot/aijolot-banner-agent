---
name: performance-audit
description: Run Lighthouse + W3C + JSON-LD validation; Auditor sub-agent decides retry routing.
metadata:
  type: hybrid
  model: gemini-3.5-flash
  sub_agent: auditor
  owner_node: 9
  ticket: GH-16, GH-NEW7
---

## Inputs
- `html: str` (rendered banner)
- `state: BannerSessionState` (for retries counter)

## Outputs
- `AuditReport` + `AuditDecision` (pass | retry_node_5 | retry_node_8 | escalate_hitl)

## Acceptance criteria
- [ ] AuditReport fields: lighthouse{perf,lcp_ms,cls}, html_w3c, schema_valid, breakpoints_render, root_cause_hint
- [ ] Auditor decision respects max 2 retries per node
- [ ] FAIL blocks publish
