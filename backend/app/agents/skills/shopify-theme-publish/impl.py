"""shopify-theme-publish skill — controlled Shopify theme publishing.

WRITE ACTION: should only be invoked after HITL approval by upstream graph/API.
"""

from __future__ import annotations

from app.agents.state import BannerSessionState, PublishResult
from app.services.shopify.publisher import configured_publisher


async def run(state: BannerSessionState) -> PublishResult:
    campaign_id = getattr(state, "campaign_id", None) or getattr(state, "id", None)
    if not campaign_id:
        raise ValueError("campaign_id is required to publish")
    team_id = getattr(state, "team_id", None) or getattr(state, "supabase_team_id", None)
    if not team_id:
        raise ValueError("team_id is required for safe dry-run publishing")
    job = configured_publisher(team_id=str(team_id)).publish_campaign(str(campaign_id))
    return PublishResult(shopify_section_id=job.shopify_resource_id or job.id, theme_id="", asset_urls=[])
