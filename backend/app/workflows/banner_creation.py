"""Banner creation workflow — orchestrates the Coordinator graph end-to-end.

Called by FastAPI routes (POST /campaigns/{id}/draft + WS /campaigns/{id}/events).
Streams node-by-node progress events to the React UI.

Implementation lands as nodes ship (GH-5..GH-19).
"""

from __future__ import annotations

import uuid

from app.agents.state import BannerSessionState


async def start_session(brand_id: str, session_id: str | None = None) -> BannerSessionState:
    return BannerSessionState(
        trace_id=str(uuid.uuid4()),
        session_id=session_id or str(uuid.uuid4()),
        brand_id=brand_id,
    )


async def run_to_audit(state: BannerSessionState) -> BannerSessionState:
    """Run nodes 1-9 (intake -> audit). Halt at node 10 awaiting HITL."""
    raise NotImplementedError("Wired in GH-5 + per-node tickets.")


async def resume_after_hitl(state: BannerSessionState) -> BannerSessionState:
    """Run nodes 11-12 (schedule or publish) after HITL decision."""
    raise NotImplementedError("Wired in GH-5 + GH-18 + GH-19.")
