"""image-asset-optimize skill — see SKILL.md. Lands in GH-13."""

from app.agents.state import BannerAssets
from app.agents.tools import image_optim


async def run(image_bytes: bytes, alt_text_hint: str) -> BannerAssets:
    return await image_optim.optimize(image_bytes, alt_text_hint=alt_text_hint)
