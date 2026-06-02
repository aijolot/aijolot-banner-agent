---
name: schedule-or-publish-route
description: Route an approved campaign to immediate publish or scheduled publish based on HITL decision and schedule state. Deterministic branching, no LLM. Node 11 in the ADK graph. WRITE-ACTION policy — HITL approval required upstream.
---

# Schedule or Publish Route

Branch the pipeline between immediate publish and scheduled publish after HITL approval.

> **Node Metadata** | node: 11 | type: deterministic | model: none | ticket: GH-18 | version: 0.2.0 | status: draft | policy: write-action

## Node Invariants

1. **Binary routing only.** Output is exactly `"immediate"` or `"scheduled"` — no third option.
2. **HITL approval required upstream.** This node must never execute without prior human approval at node 10.
3. **No side effects.** This node only decides the route — actual publish or schedule INSERT is done by node 12.
4. **Schedule presence determines route.** If any schedule data exists on state, route is `"scheduled"`.

## Graph Entry Conditions

- **Upstream:** `human_review` (node 10) must have completed.
- **State preconditions:** `state.hitl_decision is not None`, `state.hitl_decision.action in {"approve", "schedule"}`.
- **Retry re-entry:** Not applicable. `max_retries = 0` in graph.py.

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| State | `hitl_decision` | `HITLDecision` | Yes |
| State | `schedule` or `publish_schedule` | `dict \| None` | Checked for schedule data |

The skill checks for schedule presence on `state.schedule`, `state.publish_schedule`, or `hitl_decision.target_publish_at`.

## Output Encoding

- **Type:** `str` — one of `"immediate"` or `"scheduled"`.
- **Deterministic:** Same state always produces the same route.

## Data Sources

| Source | Purpose |
|--------|---------|
| State: `hitl_decision` | Approval action |
| State: `schedule` / `publish_schedule` | Schedule presence check |

No tools. No prompts. No sub-agents.

## Workflow

1. Check for schedule attribute on state (`schedule`, `publish_schedule`).
2. If schedule exists and has `starts_at` field → return `"scheduled"`.
3. If schedule exists (any truthy value) → return `"scheduled"`.
4. Otherwise → return `"immediate"`.

## Output Contract

No state field written directly. The return value tells the Coordinator which downstream path to take:
- `"immediate"` → invoke node 12 (`shopify-theme-publish`) immediately.
- `"scheduled"` → INSERT schedule row, pg_cron fires node 12 at `target_publish_at`.

Return type: `str`

## Data Provenance

| Output field | Provenance |
|-------------|-----------|
| Route string | `[DETERMINISTIC]` — computed from schedule presence on state |

## Pre/Post Conditions

**Pre:**
- `state.hitl_decision is not None`
- `state.hitl_decision.action in {"approve", "schedule"}`

**Post:**
- Return value is exactly `"immediate"` or `"scheduled"`

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| `hitl_decision` is None | Coordinator should never invoke this node — if reached, raise `ValueError` |
| `hitl_decision.action == "reject"` | Coordinator should not route here — if reached, raise `ValueError` |
| Schedule data malformed | Treat as `"scheduled"` (any truthy schedule value → scheduled path) |
| No schedule data at all | Route to `"immediate"` — safe default |

## Quality Criteria

- [ ] Returns `"immediate"` when no schedule data exists
- [ ] Returns `"scheduled"` when `state.schedule.starts_at` is populated
- [ ] Returns `"scheduled"` when `state.publish_schedule` is truthy
- [ ] Raises if `hitl_decision.action` is not `"approve"` or `"schedule"`
- [ ] No side effects (no DB writes, no API calls)

## Guardrails

- Never return a value other than `"immediate"` or `"scheduled"`.
- Never perform the actual publish or schedule INSERT — that is node 12's responsibility.
- Never bypass HITL check — the Coordinator must validate approval before invoking this node.
- Never default to `"scheduled"` when schedule data is ambiguous — prefer `"immediate"` (fail-safe: publish now is visible, missed schedule is not).

## Human Review Required

**Indirectly.** This node does not request review, but it requires HITL approval from node 10. The Coordinator validates `hitl_decision.action` before invoking.

## References

- State model: `HITLDecision`, `BannerSessionState` → `backend/app/agents/state.py`
- Upstream skill: `hitl-review-handoff` (node 10)
- Downstream skill: `shopify-theme-publish` (node 12)
- Design reference: Source Technical Design §7 — schedule_or_publish branching
