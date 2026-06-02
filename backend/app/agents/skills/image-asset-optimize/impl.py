"""image-asset-optimize skill — see SKILL.md."""

from __future__ import annotations

from typing import Any

from app.agents.state import BannerAssets
from app.agents.tools import image_optim
from app.services.banners.asset_service import BannerAssetService


async def run(
    image_bytes: bytes,
    alt_text_hint: str,
    *,
    campaign_id: str | None = None,
    revision_id: str | None = None,
    banner_variant_id: str | None = None,
    mime_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    image_prompt: str | None = None,
    asset_service: BannerAssetService | None = None,
) -> BannerAssets:
    return await image_optim.optimize(
        image_bytes,
        alt_text_hint=alt_text_hint,
        campaign_id=campaign_id,
        revision_id=revision_id,
        banner_variant_id=banner_variant_id,
        mime_type=mime_type,
        metadata=metadata,
        image_prompt=image_prompt,
        asset_service=asset_service,
    )
