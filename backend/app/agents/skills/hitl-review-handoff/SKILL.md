---
name: hitl-review-handoff
description: Pause the ADK banner pipeline at node 10 for mandatory human review. Receives AuditReport and full creative output, emits SSE review event to React Canvas UI, waits for HITLDecision (approve/reject/edit_request/schedule), writes decision to state, resumes pipeline. No bypass exists. Node 10 in the ADK graph.
---

# HITL Review Handoff

Mandatory human review gate — pause the pipeline and hand off to the React Canvas UI.

> **Node Metadata** | node: 10 | type: hitl | model: none | ticket: GH-30 | version: 0.1.0 | status: draft

## Node Invariants

1. **MANDATORY. No bypass.** The Coordinator must never skip this node. Creative output never publishes without human approval, even if audit passes cleanly.
2. **Pipeline fully suspended.** No downstream node (11, 12) executes until a human decision arrives.
3. **No auto-approve.** Timeout, error, or missing reviewer defaults to "expired" — never to "approved".
4. **All four decision actions supported.** `approve`, `reject`, `edit_request`, `schedule` — no other values accepted.

## Graph Entry Conditions

- **Upstream:** `audit` (node 9) must have completed with decision `"human_review_required"` or `"escalate_hitl"`.
- **State preconditions:**
  - `state.audit_report is not None`
  - `state.html_standalone is not None`
  - `state.concept is not None`
  - `state.assets is not None`
- **Not re-entered on retry.** When HITL rejects, the Coordinator routes to node 5 for concept re-drafting — not back to this node. This node is entered exactly once per pipeline run (unless the pipeline re-runs from the beginning after reject → retry → re-audit).

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| State | `audit_report` | `AuditReport` | Yes — full audit results for reviewer |
| State | `html_standalone` | `str` | Yes — for preview rendering |
| State | `liquid_section` | `str` | Yes — for Shopify preview |
| State | `assets` | `BannerAssets` | Yes — for visual preview |
| State | `concept` | `Concept` | Yes — for copy/layout review |
| State | `brand_context` | `BrandContext` | Yes — for brand compliance check |
| State | `variants` | `list[Variant]` | Yes — for variant review |

## Output Encoding

- **Model:** `app.agents.state.HITLDecision` (Pydantic)
- **Fields:**
  - `action: str` — one of `"approve"`, `"reject"`, `"edit_request"`, `"schedule"`
  - `target_publish_at: datetime | None` — only for `action="schedule"`
  - `reviewer: str` — reviewer user ID
  - `notes: str | None` — required for `reject` and `edit_request`

## Data Sources

| Source | Purpose |
|--------|---------|
| State: audit_report, html_standalone, liquid_section, assets, concept, brand_context, variants | Build review payload |
| Tool: `audit_log.emit(...)` | Emit pause/resume events |
| Frontend: SSE channel → React Canvas UI | Deliver review payload, receive decision |

No LLM. No sub-agents. No external API (other than SSE to frontend).

## Workflow

1. **Validate pre-conditions:**
   a. `audit_report` exists and is not None.
   b. `html_standalone` exists for preview.
   c. Pipeline is not already expired.
2. **Build review payload:**
   a. Audit summary: status, findings count by severity, root_cause_hint.
   b. Preview: HTML standalone (or URL if served).
   c. Brand context summary: name, palette, voice.tone.
   d. Concept summary: headline, subheadline, CTA, layout.
   e. Variant list: customer_tags with intent_deltas.
   f. Asset summary: total weight, breakpoint count, AVIF status.
3. **Emit SSE event** `hitl_review_required` with payload to frontend channel.
4. **Emit audit_log event** `{node: "human_review", event: "review_requested"}`.
5. **Suspend execution.** Pipeline awaits human decision:
   a. React Canvas UI renders preview + audit report + approval controls.
   b. Reviewer examines creative output.
   c. Reviewer selects action: approve / reject / edit_request / schedule.
6. **Receive HITLDecision** from React Canvas callback.
7. **Validate decision:**
   a. `action` must be one of the four allowed values.
   b. `reviewer` must be non-empty.
   c. If `action == "edit_request"`: `notes` must be non-empty (what to change).
   d. If `action == "schedule"`: `target_publish_at` must be a future datetime.
8. **Write state:**
   a. `state.hitl_decision = HITLDecision(...)`.
   b. If `action == "schedule"`: `state.scheduled_at = target_publish_at`.
9. **Emit audit_log event** `{node: "human_review", event: "review_completed", payload: {action, reviewer}}`.
10. **Return** `HITLDecision` to Coordinator.

The Coordinator then routes based on action:
- `approve` → node 11 (schedule_or_publish_route) → node 12 (publish)
- `schedule` → node 11 (routes to "scheduled") → node 12 (at scheduled time)
- `reject` → node 5 (re-draft concept with notes as context)
- `edit_request` → node 5 (re-draft with specific edit instructions)

## Output Contract

| State field written | Type | Description |
|---------------------|------|-------------|
| `state.hitl_decision` | `HITLDecision` | Human review decision |
| `state.scheduled_at` | `datetime \| None` | Only if action == "schedule" |

Return type: `HITLDecision`

## Data Provenance

| Output field | Provenance |
|-------------|-----------|
| `hitl_decision.action` | `[USER-PROVIDED]` — human reviewer choice |
| `hitl_decision.reviewer` | `[USER-PROVIDED]` — reviewer identity |
| `hitl_decision.target_publish_at` | `[USER-PROVIDED]` — schedule time |
| `hitl_decision.notes` | `[USER-PROVIDED]` — reviewer feedback |
| `scheduled_at` | `[DETERMINISTIC]` — copied from `hitl_decision.target_publish_at` |
| audit_log events | `[DETERMINISTIC]` — emitted by this node |

## Pre/Post Conditions

**Pre:**
- `state.audit_report is not None`
- `state.html_standalone is not None`
- `state.concept is not None`
- `state.assets is not None`
- `state.hitl_decision is None` (not already reviewed)

**Post:**
- `state.hitl_decision is not None`
- `state.hitl_decision.action in {"approve", "reject", "edit_request", "schedule"}`
- `state.hitl_decision.reviewer != ""`
- If `action == "edit_request"`: `state.hitl_decision.notes is not None and state.hitl_decision.notes != ""`
- If `action == "schedule"`: `state.scheduled_at is not None`
- audit_log contains both `review_requested` and `review_completed` events

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| `audit_report` is None | Raise `ValueError` — do not present incomplete data for review |
| SSE channel unavailable | Log error, keep pipeline suspended, retry SSE after backoff |
| Decision timeout (24h) | Mark session as `"expired"`, emit audit_log event, do NOT auto-approve |
| Invalid action value | Reject the callback, request valid action from reviewer |
| `edit_request` without notes | Reject the callback — notes are mandatory for edit requests |
| `schedule` with past datetime | Reject the callback — `target_publish_at` must be in the future |
| Reviewer ID empty | Reject the callback — reviewer identity is required |

**Critical:** The fallback for every unexpected state is to keep the pipeline paused or halt — never to auto-approve.

## Quality Criteria

- [ ] Pipeline fully suspends (no node 11/12 execution before decision)
- [ ] SSE event contains all fields needed by React Canvas for rendering
- [ ] Timeout enforced at 24h — session marked "expired", not "approved"
- [ ] All four decision actions tested: approve, reject, edit_request, schedule
- [ ] audit_log events emitted for both review_requested and review_completed
- [ ] `edit_request` without notes is rejected
- [ ] `schedule` with past datetime is rejected

## Guardrails

- **NEVER auto-approve.** The HITL gate exists because human judgment is required. Timeout = expired, not approved.
- **NEVER bypass this node.** Even if audit passes with zero findings, the human still reviews.
- **NEVER expose raw BannerSessionState to frontend.** Build a sanitized review payload with only the fields needed for review.
- **NEVER allow `edit_request` without notes.** The reviewer must specify what to change.
- **NEVER allow `schedule` with past datetime.** Validate `target_publish_at > now()`.
- **NEVER store the decision without emitting audit_log.** Traceability is mandatory.

## Human Review Required

**This node IS the human review.** It does not need additional approval for itself. The decision it produces (`approve` / `schedule`) is what gates nodes 11 and 12.

## References

- State models: `HITLDecision`, `AuditReport`, `BannerSessionState` → `backend/app/agents/state.py`
- Tool: `audit_log` → `backend/app/agents/tools/audit_log.py`
- Graph: `NodeSpec("human_review", "hitl-review-handoff", hitl=True)` → `backend/app/agents/graph.py`
- Coordinator prompt: `coordinator.md` → `backend/app/agents/prompts/coordinator.md` (HITL gate rule #1)
- Frontend: `CanvasStage.jsx`, `CanvasPanels.jsx` → `frontend/`
- Detail: `references/hitl_decision_schema.md`
- Upstream skill: `performance-audit` (node 9)
- Downstream skill: `schedule-or-publish-route` (node 11)
