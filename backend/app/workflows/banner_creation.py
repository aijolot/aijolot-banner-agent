"""Banner creation workflow — orchestrates the Coordinator graph end-to-end.

Called by FastAPI routes (POST /campaigns/{id}/draft + WS /campaigns/{id}/events).
Streams node-by-node progress events to the React UI.

Implementation lands as nodes ship (GH-5..GH-19).
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from typing import Any, cast

from app.agents.graph import NODES
from app.agents.state import BannerSessionState
from app.agents.tools import html_render, liquid_render

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

DETERMINISTIC_LAYOUT_VARIANT_KEYS: tuple[str, ...] = ("A", "B", "C")


def ordered_node_keys() -> list[str]:
    return [node.name for node in NODES]


def frontend_step_for_node(node_key: str) -> str:
    try:
        return NODE_TO_FRONTEND_STEP[node_key]
    except KeyError as exc:
        raise ValueError(f"unknown banner graph node '{node_key}'") from exc


def _load_runtime_skill(skill_id: str) -> Any:
    path = Path(__file__).resolve().parents[1] / "agents" / "skills" / skill_id / "impl.py"
    spec = importlib.util.spec_from_file_location(f"aijolot_{skill_id.replace('-', '_')}_impl", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"runtime skill not found: {skill_id}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def start_session(brand_id: str, session_id: str | None = None) -> BannerSessionState:
    return BannerSessionState(
        trace_id=str(uuid.uuid4()),
        session_id=session_id or str(uuid.uuid4()),
        brand_id=brand_id,
    )


async def run_to_audit(state: BannerSessionState) -> BannerSessionState:
    """Run the implemented render/audit segment and halt before HITL.

    Earlier nodes are implemented task-by-task. By Task 14, callers that have a
    concept and assets can run through HTML/Liquid rendering and deterministic
    audit, then stop with `audit_report.human_review_required=True`.
    """
    if state.concept is None:
        raise ValueError("state.concept is required before run_to_audit")
    if state.assets is None:
        raise ValueError("state.assets is required before run_to_audit")

    state.html_standalone = await html_render.render(state.concept, state.assets, brand=state.brand_context)
    liquid_payload = await liquid_render.render(
        state.concept,
        state.variants,
        brand=state.brand_context,
        assets=state.assets,
        placement=state.campaign.placement if state.campaign else None,
    )
    state.liquid_section = str(liquid_payload.get("section") or "")

    audit_skill = _load_runtime_skill("performance-audit")
    await audit_skill.run(state.html_standalone, state)
    return state


async def resume_after_hitl(state: BannerSessionState) -> BannerSessionState:
    """Run nodes 11-12 (schedule or publish) after HITL decision."""
    raise NotImplementedError("Wired in GH-5 + GH-18 + GH-19.")
