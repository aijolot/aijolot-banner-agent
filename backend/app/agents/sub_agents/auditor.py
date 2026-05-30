"""Auditor sub-agent — node 9 (audit, retry routing).

Model: gemini-3.5-flash (cheaper, short reasoning over JSON).
Inputs: AuditReport JSON + retrieved AuditFailure remediations from KG.
Output: retry decision — which upstream node to re-enter (5 or 8), or PASS.

Policy:
- Max 2 retries per node (tracked in BannerSessionState.retries).
- If retries exhausted, escalate to HITL with hint.
- Always emits root_cause_hint to audit_log.

Implementation deferred to GH-16 + GH-NEW7.
"""

from __future__ import annotations

import os

from app.agents.state import AuditReport, BannerSessionState


AUDITOR_MODEL = os.getenv("GEMINI_MODEL_FLASH", "gemini-3.5-flash")


class AuditDecision:
    PASS = "pass"
    RETRY_CONCEPT = "retry_node_5"
    RETRY_RENDER = "retry_node_8"
    ESCALATE_HITL = "escalate_hitl"


async def decide(state: BannerSessionState, report: AuditReport) -> str:
    """Return one of AuditDecision values."""
    raise NotImplementedError("Lands in GH-16 / GH-NEW7.")
