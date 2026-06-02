"""liquid-section-build skill — see SKILL.md."""

from typing import Any

from app.agents.state import BannerAssets, Concept, Variant
from app.agents.tools import liquid_render


async def run(
    concept: Concept,
    variants: list[Variant],
    brand,
    assets: BannerAssets | None = None,
    placement: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await liquid_render.render(concept, variants, brand=brand, assets=assets, placement=placement)
