"""hitl-review-handoff skill — node 10 (HITL gate).

Pauses the ADK pipeline and hands off to the React Canvas UI for mandatory
human review. No downstream node executes until a HITLDecision arrives.

Implementation deferred to GH-30.
"""

from __future__ import annotations

from app.agents.state import BannerSessionState, HITLDecision


async def run(state: BannerSessionState) -> HITLDecision:
    """Pause pipeline for human review and return the decision.

    In the full implementation this will:
    1. Emit SSE event with review payload to React Canvas UI
    2. Await human decision callback
    3. Validate and write state.hitl_decision
    4. Emit audit_log events for request/completion
    """
    raise NotImplementedError("HITL review handoff lands in GH-30.")
