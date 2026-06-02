"""ADK Tool: Shopify Liquid Section render with conditional variants."""

from __future__ import annotations

from typing import Any

from app.agents.state import BannerAssets, Concept, Variant
from app.services.shopify.liquid_payload_builder import build_liquid_payload


async def render(
    concept: Concept,
    variants: list[Variant],
    *,
    brand,
    assets: BannerAssets | None = None,
    placement: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_liquid_payload(concept, variants, brand=brand, assets=assets, placement=placement).as_dict()
