"""nano-banana-image-generate skill.

Generates image bytes through the image-provider boundary and attaches soft usage
warning metadata. Raw bytes remain in-memory; optimization/upload is Task 13.
"""

from __future__ import annotations

from typing import Any

from app.agents.tools import nano_banana_image
from app.services.banners.usage_guard_service import UsageGuardService, get_default_usage_guard_service
from app.services.gemini.image_provider import ImageProvider


async def run(
    prompt: str | Any = "",
    *,
    concept: Any | None = None,
    context: dict[str, Any] | None = None,
    user_id: str | None = None,
    team_id: str | None = None,
    campaign_id: str | None = None,
    aspect_ratio: str = "16:9",
    provider: ImageProvider | None = None,
    usage_guard: UsageGuardService | None = None,
) -> dict[str, Any]:
    image_prompt = _resolve_prompt(prompt=prompt, concept=concept, context=context)
    response = await nano_banana_image.generate(
        image_prompt,
        aspect_ratio=aspect_ratio,
        user_id=user_id,
        campaign_id=campaign_id,
        provider=provider,
        metadata={"context_keys": sorted((context or {}).keys())},
    )
    guard = usage_guard or get_default_usage_guard_service()
    usage_result = guard.record_image_generation(
        user_id=user_id,
        team_id=team_id,
        campaign_id=campaign_id,
        provider=response.provider,
        model=response.model,
        estimated_cost_usd=response.usage.get("estimated_cost_usd"),
        metadata={"mime_type": response.mime_type, "size_bytes": response.size_bytes},
    )
    return {
        "image_bytes": response.image_bytes,
        "mime_type": response.mime_type,
        "provider": response.provider,
        "model": response.model,
        "prompt": response.prompt,
        "aspect_ratio": response.aspect_ratio,
        "usage": response.usage,
        "metadata": {
            **response.metadata,
            "size_bytes": response.size_bytes,
            "usage_guard": usage_result.to_metadata(),
        },
    }


def _resolve_prompt(*, prompt: Any, concept: Any | None, context: dict[str, Any] | None) -> str:
    candidates: list[Any] = []
    if prompt:
        candidates.append(prompt)
    if concept is not None:
        candidates.extend([
            getattr(concept, "image_prompt", None),
            concept.get("image_prompt") if isinstance(concept, dict) else None,
        ])
    if context:
        candidates.extend([context.get("prompt"), context.get("image_prompt")])
    for candidate in candidates:
        if candidate is None:
            continue
        value = str(candidate).strip()
        if value:
            return value
    raise ValueError("Image generation prompt is required")
