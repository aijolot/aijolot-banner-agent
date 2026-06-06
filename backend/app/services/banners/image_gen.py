"""Shared hero-image generation with cost gating + safe provider fallback.

Reserves the daily Gemini cost guard only for a *real* provider; on a denial or
an `ImageProviderUnavailable` (e.g. no GOOGLE_API_KEY) it degrades to the free
deterministic fake provider so the banner always renders. Used by the F5
orchestrator and the F8 art-generation service.
"""

from __future__ import annotations

from typing import Any

from app.workflows.banner_creation import _load_runtime_skill

# Nominal estimate for a single paid hero image generation (USD).
EST_IMAGE_USD = 0.04


async def generate_image(
    refined_prompt: str,
    *,
    settings: Any,
    cost_guard: Any,
    campaign_id: str | None = None,
    aspect_ratio: str = "16:9",
    concept: Any = None,
    est_usd: float = EST_IMAGE_USD,
    reference_images: tuple[tuple[bytes, str], ...] = (),
) -> tuple[bytes, dict[str, Any], float]:
    from app.agents.tools import nano_banana_image
    from app.services.gemini.fake_image_provider import FakeImageProvider
    from app.services.gemini.image_provider import ImageProviderUnavailable

    image_skill = _load_runtime_skill("nano-banana-image-generate")

    provider = nano_banana_image.select_provider(settings=settings)
    is_real = type(provider).__name__ != "FakeImageProvider"
    cost = 0.0
    if is_real:
        reservation = cost_guard.check_and_reserve(est_usd)
        if reservation.allowed:
            cost = reservation.estimated_usd
        else:
            provider = FakeImageProvider()  # cost cap hit → free fallback
            is_real = False

    try:
        result = await image_skill.run(
            refined_prompt, concept=concept, campaign_id=campaign_id, aspect_ratio=aspect_ratio,
            provider=provider, reference_images=reference_images,
        )
    except ImageProviderUnavailable:
        # Real provider not usable (e.g. no GOOGLE_API_KEY): degrade to the free
        # fake provider so the banner still renders.
        if not is_real:
            raise
        cost = 0.0
        result = await image_skill.run(
            refined_prompt, concept=concept, campaign_id=campaign_id, aspect_ratio=aspect_ratio,
            provider=FakeImageProvider(), reference_images=reference_images,
        )
    meta = {k: v for k, v in result.items() if k != "image_bytes"}
    meta["size_bytes"] = result.get("metadata", {}).get("size_bytes")
    meta["is_real_provider"] = is_real
    return result["image_bytes"], meta, cost
