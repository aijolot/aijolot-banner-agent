"""ADK Tool: multi-breakpoint image optimization (Pillow + pillow-avif-plugin).

Lands in GH-13. Generates 4 breakpoints (320/768/1280/1920) in WebP + AVIF
plus 1 JPG fallback. Enforces weight cap <80KB @ 1280 WebP.
"""

from __future__ import annotations

from app.agents.state import BannerAssets


async def optimize(image_bytes: bytes, *, alt_text_hint: str) -> BannerAssets:
    raise NotImplementedError("Lands in services/banners/image_optimizer.py + GH-13.")
