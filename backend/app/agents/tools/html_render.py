"""ADK Tool: standalone HTML render (Concept + assets -> HTML + meta + JSON-LD)."""

from __future__ import annotations

from app.agents.state import BannerAssets, Concept
from app.services.banners.html_renderer import render_banner_preview


async def render(concept: Concept, assets: BannerAssets, *, brand) -> str:
    return render_banner_preview(concept, assets, brand=brand).html
