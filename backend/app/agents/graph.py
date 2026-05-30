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


def build_graph() -> Callable[[BannerSessionState], BannerSessionState]:
    """Return the compiled ADK runnable.

    Implementation deferred to GH-5 (skeleton) + per-node tickets.
    This function exists so callers (workflows, API) can depend on a stable
    factory signature.
    """
    raise NotImplementedError("Graph wiring lands in GH-5 + per-node tickets (GH-8..GH-19).")
