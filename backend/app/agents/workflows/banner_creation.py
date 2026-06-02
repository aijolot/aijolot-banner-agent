"""Banner creation workflow — entry points for the ADK pipeline.

Provides high-level functions that the API layer calls to start and
resume banner generation pipelines.
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncGenerator

from app.agents.pipeline_runner import (
    FRONTEND_PROGRESS_STEPS,
    NODE_TO_FRONTEND_STEP,
    get_pipeline_runner,
)
from app.agents.state import BannerSessionState


async def start_session(
    *,
    brand_id: str,
    campaign: dict[str, Any],
    session_id: str | None = None,
    trace_id: str | None = None,
) -> str:
    """Initialize a pipeline session and return the session_id.

    Does NOT run the pipeline — call run_to_review() next.
    """
    return session_id or str(uuid.uuid4())


async def run_to_review(
    *,
    brand_id: str,
    campaign: dict[str, Any],
    session_id: str | None = None,
    trace_id: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Run the pre-review pipeline (nodes 1, 3-9).

    Yields progress events as dicts with node_key, frontend_step, status.
    The final event has status="awaiting_review" with the session state
    for HITL inspection.
    """
    runner = get_pipeline_runner()
    async for event in runner.start(
        brand_id=brand_id,
        campaign=campaign,
        session_id=session_id,
        trace_id=trace_id,
    ):
        yield event


async def resume_after_review(
    *,
    session_id: str,
    hitl_decision: dict[str, Any],
) -> AsyncGenerator[dict[str, Any], None]:
    """Run the post-review pipeline (nodes 11-12) after HITL approval.

    The hitl_decision dict must contain:
      - action: "approve" | "schedule"
      - reviewer: str
      - notes: str | None
      - target_publish_at: str | None (ISO datetime for schedule)
    """
    runner = get_pipeline_runner()
    async for event in runner.resume(
        session_id=session_id,
        hitl_decision=hitl_decision,
    ):
        yield event


def get_progress_steps() -> list[dict[str, str]]:
    """Return the frontend progress step definitions."""
    return list(FRONTEND_PROGRESS_STEPS)


def get_node_step_mapping() -> dict[str, str]:
    """Return the node_key → frontend_step mapping."""
    return dict(NODE_TO_FRONTEND_STEP)
