"""12-node ADK graph for the Shopify Banner Agent.

Topology (blueprint §3):
  1 load_brand_context
  2 intake_campaign_idea
  3 capture_user_personalization
  4 research_best_practices (KG retrieve)
  5 draft_banner_concept            -> CreativeDirector sub-agent
  6 generate_image (Nano Banana Pro)
  7 optimize_assets
  8 render_html (+ liquid)
  9 audit                            -> Auditor sub-agent (retry routing)
 10 human_review (HITL — React UI)
 11 schedule_or_publish
 12 publish_to_shopify

The graph is built declaratively; concrete ADK wiring is filled per ticket
(GH-8..GH-19). This file is the single source of truth for node order +
retry policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.agents.state import BannerSessionState


@dataclass
class NodeSpec:
    name: str
    skill_id: str
    upstream: list[str]
    max_retries: int = 0  # only nodes 5/8 can be re-entered from audit
    hitl: bool = False


NODES: list[NodeSpec] = [
    NodeSpec("load_brand_context", "brand-context-load", []),
    NodeSpec("intake_campaign_idea", "campaign-intake", ["load_brand_context"]),
    NodeSpec("capture_user_personalization", "user-personalization", ["intake_campaign_idea"]),
    NodeSpec("research_best_practices", "best-practices-retrieve", ["capture_user_personalization"]),
    NodeSpec("draft_banner_concept", "banner-concept-draft", ["research_best_practices"], max_retries=2),
    NodeSpec("generate_image", "nano-banana-image-generate", ["draft_banner_concept"], max_retries=1),
    NodeSpec("optimize_assets", "image-asset-optimize", ["generate_image"]),
    NodeSpec("render_html", "banner-html-seo-render", ["optimize_assets"]),
    NodeSpec("audit", "performance-audit", ["render_html"]),
    NodeSpec("human_review", "hitl-review-handoff", ["audit"], hitl=True),
    NodeSpec("schedule_or_publish", "schedule-or-publish-route", ["human_review"]),
    NodeSpec("publish_to_shopify", "shopify-theme-publish", ["schedule_or_publish"]),
]


def build_graph():
    """Return the pre-review ADK Workflow (nodes 1, 3-9).

    The pipeline runs from brand load through audit with a conditional
    retry loop. Node 2 (intake) is multi-turn and handled by the API
    SSE endpoint. Nodes 11-12 (post-HITL) are in build_post_review_graph().
    """
    from app.agents.pipeline import build_pre_review_pipeline

    return build_pre_review_pipeline()


def build_post_review_graph():
    """Return the post-review ADK Workflow (nodes 11-12).

    Runs after HITL approval. Expects session.state to have
    hitl_decision populated.
    """
    from app.agents.pipeline import build_post_review_pipeline

    return build_post_review_pipeline()
