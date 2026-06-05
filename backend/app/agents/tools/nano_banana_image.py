"""ADK Tool: Nano Banana image generation via a safe provider boundary."""

from __future__ import annotations

import os
from typing import Any

from app.core.settings import Settings
from app.services.gemini.fake_image_provider import FakeImageProvider
from app.services.gemini.image_provider import (
    GeminiImageProvider,
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageProvider,
    ImageProviderUnavailable,
)

_REAL_PROVIDER_NAMES = {"gemini", "nano-banana", "nano_banana"}
_FAKE_PROVIDER_NAMES = {"", "fake", "deterministic", "disabled", "local"}


def select_provider(*, settings: Settings | None = None, provider_name: str | None = None) -> ImageProvider:
    """Return an image provider without making network calls.

    Safety rule: real Gemini is used only when the provider is explicitly set in
    the environment or passed to this function. The settings default remains
    backward-compatible, but an unset IMAGE_GENERATION_PROVIDER resolves to fake.
    """

    explicit_env = os.getenv("IMAGE_GENERATION_PROVIDER")
    explicit_settings = settings.image_generation_provider if settings is not None else None
    selected = provider_name if provider_name is not None else explicit_env
    if selected is None and explicit_settings is not None:
        selected = explicit_settings
    if selected is None:
        return FakeImageProvider()

    normalized = selected.strip().lower()
    if normalized in _FAKE_PROVIDER_NAMES:
        return FakeImageProvider()
    if normalized in _REAL_PROVIDER_NAMES:
        return GeminiImageProvider(settings=settings)
    raise ImageProviderUnavailable(f"Unsupported image generation provider: {normalized}")


async def generate(
    prompt: str,
    *,
    aspect_ratio: str = "16:9",
    width: int | None = None,
    height: int | None = None,
    user_id: str | None = None,
    campaign_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    provider: ImageProvider | None = None,
    provider_name: str | None = None,
    settings: Settings | None = None,
    reference_images: tuple[tuple[bytes, str], ...] = (),
) -> ImageGenerationResponse:
    """Generate one image and return bytes plus provider metadata."""

    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        raise ValueError("Image generation prompt is required")

    selected_provider = provider or select_provider(settings=settings, provider_name=provider_name)
    request = ImageGenerationRequest(
        prompt=clean_prompt,
        aspect_ratio=aspect_ratio,
        width=width,
        height=height,
        user_id=user_id,
        campaign_id=campaign_id,
        metadata=metadata or {},
        reference_images=tuple(reference_images or ()),
    )
    return await selected_provider.generate(request)
