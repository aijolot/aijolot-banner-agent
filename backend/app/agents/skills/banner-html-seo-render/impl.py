"""banner-html-seo-render skill — see SKILL.md."""

from app.agents.state import BannerAssets, Concept
from app.agents.tools import html_render


async def run(concept: Concept, assets: BannerAssets, brand) -> str:
    return await html_render.render(concept, assets, brand=brand)
