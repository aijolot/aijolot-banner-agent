---
name: performance-audit
description: Run parallel W3C + Lighthouse + JSON-LD schema validation on rendered HTML banner. Aggregate findings by severity, decide retry routing (pass, retry_node_5, retry_node_8, escalate_hitl). Hybrid skill with Auditor sub-agent for LLM-based reasoning over failures. Node 9 in the ADK graph.
---

# Performance Audit

Validate the rendered banner against quality gates and decide whether to pass, retry, or escalate.

> **Node Metadata** | node: 9 | type: hybrid | model: gemini-3.5-flash | sub_agent: auditor | ticket: GH-16, GH-NEW7 | version: 0.2.0 | status: draft

## Node Invariants

1. **Three-tool parallel audit.** Always runs W3C, Schema, and Lighthouse validations — never skips one.
2. **FAIL blocks publish.** Any `severity: "fail"` finding prevents the banner from reaching node 10 without resolution.
3. **Max 2 retries per upstream node.** Tracked in `state.retries`. After exhaustion → escalate to HITL.
4. **Audit log always emitted.** Every audit run produces an `audit_completed` event regardless of outcome.
5. **Human review always required.** Even on "pass", the banner goes to HITL (node 10).

## Graph Entry Conditions

- **Upstream:** `render_html` (node 8) must have completed.
- **State preconditions:** `state.html_standalone is not None`, `state.assets is not None` (for weight report).
- **Retry re-entry:** This node is re-entered after upstream retry (node 5 or 8 re-runs). The audit itself is not retried — it always runs fresh.

## Expected Inputs

| Source | Field | Type | Required |
|--------|-------|------|----------|
| Function param | `html` | `str` | Yes — rendered HTML from node 8 |
| Function param | `state` | `BannerSessionState` | Yes — for assets weight + retries tracking |

## Output Encoding

- **Return type:** `tuple[AuditReport, str]` — report + decision string.
- **AuditReport model:** `app.agents.state.AuditReport` (Pydantic)
- **Decision values:** `"pass"`, `"retry_node_5"`, `"retry_node_8"`, `"escalate_hitl"`, `"human_review_required"`
- **Findings:** list of `{severity, code, message, source}` dicts.

## Data Sources

| Source | Purpose |
|--------|---------|
| Tool: `audit_w3c.validate(html)` | HTML W3C validation |
| Tool: `audit_schema.validate(html)` | JSON-LD schema validation |
| Tool: `audit_lighthouse.run(html=html)` | Lighthouse performance metrics |
| Tool: `audit_log.emit(...)` | Event emission to audit trail |
| State: `state.assets` | Asset weight report |
| State: `state.retries` | Retry count tracking |
| Sub-agent: `auditor.py` | LLM reasoning over failures (deferred: GH-NEW7) |
| Prompt: `auditor.md` | Auditor decision rules |

## Workflow

1. **Run 3 validations in parallel:**
   a. `audit_w3c.validate(html)` → `{errors: [], warnings: []}`
   b. `audit_schema.validate(html)` → `{valid: bool, errors: []}`
   c. `audit_lighthouse.run(html=html)` → `{performance, lcp_ms, cls, seo, mode}`
2. **Compute asset weight report** from `state.assets.optimization_report`:
   - ≤300KB → pass
   - 300-600KB → warn
   - \>600KB → fail
3. **Aggregate findings** by source (w3c, schema, lighthouse, assets):
   - W3C errors → `severity: "fail"`, W3C warnings → `severity: "warn"`
   - Schema errors → `severity: "fail"`
   - Lighthouse performance < 70 → `severity: "fail"`, < 90 → `severity: "warn"`
   - Lighthouse mock/manual → `severity: "warn"` with label
   - Asset weight > budget → severity from weight report
   - AVIF skipped → `severity: "warn"`
4. **Determine status:** `fail` if any finding is fail, `warn` if any warning, else `pass`.
5. **Determine decision:**
   - If status is `pass` or `warn` → `"human_review_required"` (proceed to HITL)
   - If status is `fail` → `"escalate_hitl"` (current impl). Post GH-NEW7: Auditor sub-agent decides `retry_node_5` vs `retry_node_8` vs `escalate_hitl`.
6. **Build root_cause_hint** from top 4 findings.
7. **Build AuditReport** with all fields populated.
8. **Write** `state.audit_report = report`.
9. **Emit** audit_log event with status, decision, findings, avif_skipped.
10. **Return** `(report, decision)`.

## Output Contract

| State field written | Type | Description |
|---------------------|------|-------------|
| `state.audit_report` | `AuditReport` | Complete audit results |

Return type: `tuple[AuditReport, str]`

## Data Provenance

| Output field | Provenance |
|-------------|-----------|
| `html_w3c` | `[DETERMINISTIC]` — from `audit_w3c` tool |
| `lighthouse` | `[DETERMINISTIC]` — from `audit_lighthouse` tool (mock/manual in MVP) |
| `schema_valid` | `[DETERMINISTIC]` — from `audit_schema` tool |
| `schema_report` | `[DETERMINISTIC]` — from `audit_schema` tool |
| `breakpoints_render` | `[DETERMINISTIC]` — hardcoded `{mobile: true, tablet: true, desktop: true}` in MVP |
| `root_cause_hint` | `[DETERMINISTIC]` — aggregated from findings |
| `overall_pass` | `[DETERMINISTIC]` — computed from status |
| `findings` | `[DETERMINISTIC]` — aggregated from all tools |
| `asset_weight_report` | `[DETERMINISTIC]` — from state.assets |
| Decision string | `[DETERMINISTIC]` (current) / `[LLM-GENERATED]` (post GH-NEW7, Auditor sub-agent) |

## Pre/Post Conditions

**Pre:**
- `state.html_standalone is not None` (html param)
- `state.assets is not None` (for weight report)

**Post:**
- `state.audit_report is not None`
- `state.audit_report.status in {"pass", "warn", "fail"}`
- `state.audit_report.findings is not None` (may be empty list)
- audit_log event emitted with `node: "audit"`
- Decision is one of: `"pass"`, `"human_review_required"`, `"retry_node_5"`, `"retry_node_8"`, `"escalate_hitl"`

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| `audit_w3c` tool fails | Record as `severity: "warn"` finding, continue audit — do NOT skip |
| `audit_lighthouse` tool fails | Record as mock/manual warning, continue — Lighthouse is optional in MVP |
| `audit_schema` tool fails | Record as `severity: "warn"` finding, continue |
| All 3 tools fail | `status: "warn"`, `decision: "human_review_required"` — let human decide |
| AVIF assets skipped | Record `avif_skipped: true` finding with severity warn — not a blocker |
| Retries exhausted (≥2 per node) | `decision: "escalate_hitl"` — let human decide |

**Key:** Audit never auto-passes or auto-fails in isolation. The decision always routes to human review or retry.

See `references/audit_gate_thresholds.md` for threshold values.

## Quality Criteria

- [ ] AuditReport includes: `lighthouse{perf, lcp_ms, cls}`, `html_w3c`, `schema_valid`, `breakpoints_render`, `root_cause_hint`
- [ ] Auditor decision respects max 2 retries per node
- [ ] FAIL status blocks direct publish (routes to escalate or retry)
- [ ] PASS/WARN status routes to human_review_required
- [ ] 3 audit tools run in parallel (not sequential)
- [ ] audit_log event emitted with findings summary
- [ ] AVIF skip produces warning, not failure

## Guardrails

- Never auto-pass without running all 3 validations — even if one is mock/manual.
- Never auto-publish on pass — always route to HITL (node 10).
- Never retry more than 2x per upstream node — escalate instead.
- Never suppress findings — all errors/warnings must appear in the report.
- Never mark Lighthouse mock scores as "live" — always label as `mode: "mock_manual"`.

## Human Review Required

**Indirectly.** This node routes to HITL (node 10) on pass/warn. On fail, it either retries upstream or escalates to HITL. No direct human approval at this node — the decision is automated.

## References

- Tool: `audit_w3c` → `backend/app/agents/tools/audit_w3c.py`
- Tool: `audit_schema` → `backend/app/agents/tools/audit_schema.py`
- Tool: `audit_lighthouse` → `backend/app/agents/tools/audit_lighthouse.py`
- Tool: `audit_log` → `backend/app/agents/tools/audit_log.py`
- Sub-agent: `auditor` → `backend/app/agents/sub_agents/auditor.py`
- Prompt: `auditor.md` → `backend/app/agents/prompts/auditor.md`
- State model: `AuditReport` → `backend/app/agents/state.py`
- Detail: `references/audit_gate_thresholds.md`
- Upstream skills: `banner-html-seo-render` (node 8), `liquid-section-build` (node 8)
- Downstream skill: `hitl-review-handoff` (node 10)
