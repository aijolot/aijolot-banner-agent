"""Shared video generation with cost gating + honest degradation (C2).

Veo is expensive (~$0.40/s → ~$2.40 per 6s clip), so it sits behind a DOUBLE
gate: ``settings.video_generation_enabled`` AND the cost guard. A denial or a
provider failure NEVER silently fakes a video in production — the caller gets
``(None, meta)`` and degrades the banner to its full-picture image. The fake
provider is used only when explicitly selected (demo/tests).
"""

from __future__ import annotations

from typing import Any

# Nominal Veo estimate per generated second (USD).
EST_VIDEO_USD_PER_SECOND = 0.40


async def generate_video(
    prompt: str,
    *,
    settings: Any,
    cost_guard: Any,
    campaign_id: str | None = None,
    duration_seconds: int = 6,
    aspect_ratio: str = "16:9",
    reference_image: tuple[bytes, str] | None = None,
) -> tuple[Any | None, dict[str, Any], float]:
    """Returns (response | None, meta, cost). ``None`` → degrade to image."""
    from app.agents.tools import veo_video
    from app.services.gemini.video_provider import VideoGenerationRequest, VideoProviderUnavailable

    if not bool(getattr(settings, "video_generation_enabled", False)):
        return None, {"degraded": True, "reason": "video_generation_disabled"}, 0.0

    try:
        provider = veo_video.select_provider(settings=settings)
    except VideoProviderUnavailable as exc:
        return None, {"degraded": True, "reason": f"provider_unavailable: {exc}"}, 0.0
    is_real = type(provider).__name__ != "FakeVideoProvider"

    request = VideoGenerationRequest(
        prompt=prompt,
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        campaign_id=campaign_id,
        reference_image=reference_image,
    )
    cost = 0.0
    if is_real:
        estimate = EST_VIDEO_USD_PER_SECOND * request.clamped_duration()
        reservation = cost_guard.check_and_reserve(estimate)
        if not reservation.allowed:
            # NEVER a silent fake in production — degrade to the image banner.
            return None, {"degraded": True, "reason": "cost_cap", "estimated_usd": estimate}, 0.0
        cost = reservation.estimated_usd

    try:
        response = await provider.generate(request)
    except VideoProviderUnavailable as exc:
        return None, {"degraded": True, "reason": f"generation_failed: {exc}"}, 0.0
    except Exception as exc:  # noqa: BLE001 — degradation must be explicit, not a crash
        return None, {"degraded": True, "reason": f"generation_failed: {type(exc).__name__}"}, 0.0

    meta = {
        "provider": response.provider,
        "model": response.model,
        "duration_seconds": response.duration_seconds,
        "size_bytes": len(response.video_bytes),
        "is_real_provider": is_real,
        "degraded": False,
    }
    return response, meta, cost


def motion_prompt(image_prompt: str) -> str:
    """Derive the Veo motion prompt from the (already sanitized) scene prompt."""
    return (
        image_prompt.rstrip(". ")
        + ". Subtle seamless loop: slow cinematic camera drift, gentle ambient motion "
        "(light, fabric, particles), no cuts, no zoom bursts, loop-friendly first and last frames. "
        "ABSOLUTELY NO text, captions, logos or watermarks in the video."
    )
