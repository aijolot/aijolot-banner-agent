"""Banner creation workflow — orchestrates the Coordinator graph end-to-end.

Called by FastAPI routes (POST /campaigns/{id}/draft + WS /campaigns/{id}/events).
Streams node-by-node progress events to the React UI.

Implementation lands as nodes ship (GH-5..GH-19).
"""

from __future__ import annotations

import uuid

from typing import cast

from app.agents.graph import NODES
from app.agents.state import BannerSessionState

FRONTEND_PROGRESS_STEPS: tuple[dict[str, object], ...] = (
    {
        "key": "intake_context",
        "label": "Intake & context",
        "node_keys": (
            "load_brand_context",
            "intake_campaign_idea",
            "capture_user_personalization",
            "research_best_practices",
        ),
    },
    {"key": "concept", "label": "Banner concept", "node_keys": ("draft_banner_concept",)},
    {"key": "image", "label": "Image & assets", "node_keys": ("generate_image", "optimize_assets")},
    {"key": "render_audit", "label": "Render & audit", "node_keys": ("render_html", "audit")},
    {
        "key": "review_publish",
        "label": "Review & publish",
        "node_keys": ("human_review", "schedule_or_publish", "publish_to_shopify"),
    },
)

NODE_TO_FRONTEND_STEP: dict[str, str] = {
    node_key: str(step["key"])
    for step in FRONTEND_PROGRESS_STEPS
    for node_key in cast(tuple[str, ...], step["node_keys"])
}


def ordered_node_keys() -> list[str]:
    return [node.name for node in NODES]


def frontend_step_for_node(node_key: str) -> str:
    try:
        return NODE_TO_FRONTEND_STEP[node_key]
    except KeyError as exc:
        raise ValueError(f"unknown banner graph node '{node_key}'") from exc


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
