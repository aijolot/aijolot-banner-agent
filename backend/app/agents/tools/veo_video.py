"""Veo video provider selector (C2) — mirror of nano_banana_image.select_provider.

Safety rule: the real (expensive) Veo provider is used ONLY when explicitly
selected via VIDEO_GENERATION_PROVIDER (or settings/argument). Unset → fake.
"""

from __future__ import annotations

import os

from app.core.settings import Settings
from app.services.gemini.fake_video_provider import FakeVideoProvider
from app.services.gemini.video_provider import (
    GeminiVeoProvider,
    VideoProvider,
    VideoProviderUnavailable,
)

_FAKE_PROVIDER_NAMES = {"fake", "mock", "deterministic", "local"}
_REAL_PROVIDER_NAMES = {"gemini", "veo", "gemini-veo"}


def select_provider(*, settings: Settings | None = None, provider_name: str | None = None) -> VideoProvider:
    explicit_env = os.getenv("VIDEO_GENERATION_PROVIDER")
    explicit_settings = settings.video_generation_provider if settings is not None else None
    selected = provider_name if provider_name is not None else explicit_env
    if selected is None and explicit_settings:
        selected = explicit_settings
    if selected is None:
        return FakeVideoProvider()
    normalized = selected.strip().lower()
    if normalized in _FAKE_PROVIDER_NAMES:
        return FakeVideoProvider()
    if normalized in _REAL_PROVIDER_NAMES:
        return GeminiVeoProvider(settings=settings)
    raise VideoProviderUnavailable(f"Unsupported video generation provider: {normalized}")
