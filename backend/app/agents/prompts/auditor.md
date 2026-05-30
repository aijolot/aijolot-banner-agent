# Auditor prompt (performance-audit skill)

Model: `gemini-3.5-flash` · Output: `AuditDecision`

Given an `AuditReport` and a list of relevant `AuditFailure` docs from KG, decide:
- `pass` if all gates met (Lighthouse Perf ≥90, W3C valid, schema valid, all breakpoints render, weight cap respected)
- `retry_node_5` if the root cause is creative (palette contrast, copy length, prohibited words)
- `retry_node_8` if the root cause is rendering (oversize image, missing alt, schema malformed, srcset issue)
- `escalate_hitl` if retries exhausted OR root cause ambiguous

Always populate `root_cause_hint` for the audit_log even when passing (use "n/a").
