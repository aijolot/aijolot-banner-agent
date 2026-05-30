"""ADK Tool: standalone HTML render (Concept + assets -> HTML + meta + JSON-LD).

Lands in GH-14. Output includes:
- <picture> with srcset (WebP/AVIF + JPG fallback)
- og:title, og:description, og:image meta tags
- JSON-LD PromotionalOffer

Templates live in backend/app/templates/ (Jinja2).
"""

from __future__ import annotations

from app.agents.state import BannerAssets, Concept


async def render(concept: Concept, assets: BannerAssets, *, brand) -> str:
    raise NotImplementedError("Lands in services/banners/html_renderer.py + GH-14.")
