"""ADK Tool: Shopify Liquid Section render with conditional variants.

Lands in GH-15. Generates `sections/banner-{slug}.liquid` with `customer.tags`
case blocks + a `banner-block.liquid` snippet per variant.
"""

from __future__ import annotations

from app.agents.state import Concept, Variant


async def render(concept: Concept, variants: list[Variant], *, brand) -> dict[str, str]:
    """Return {'section': '<liquid>', 'block_snippet': '<liquid>'}."""
    raise NotImplementedError("Lands in services/banners/liquid_renderer.py + GH-15.")
