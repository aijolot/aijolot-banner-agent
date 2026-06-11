"""Video generation provider boundary (C2) — mirror of image_provider.py.

``GeminiVeoProvider`` drives Veo 3.1 through the google-genai SDK's
long-running ``generate_videos`` operation (poll until done, bounded). The
deterministic ``FakeVideoProvider`` lives in fake_video_provider.py.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.settings import Settings

DEFAULT_VEO_MODEL = "veo-3.1-generate-preview"
_POLL_SECONDS = 5.0
_POLL_TIMEOUT_SECONDS = 300.0
MIN_DURATION_S, MAX_DURATION_S = 4, 8


class VideoProviderUnavailable(RuntimeError):
    """Raised when a real provider cannot be used (no key, SDK, or API error)."""


@dataclass(frozen=True, slots=True)
class VideoGenerationRequest:
    prompt: str
    duration_seconds: int = 6
    aspect_ratio: str = "16:9"
    campaign_id: str | None = None
    # Image-to-video: the banner's poster frame anchors the clip.
    reference_image: tuple[bytes, str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def clamped_duration(self) -> int:
        return max(MIN_DURATION_S, min(MAX_DURATION_S, int(self.duration_seconds or 6)))


@dataclass(frozen=True, slots=True)
class VideoGenerationResponse:
    video_bytes: bytes
    mime_type: str
    poster_bytes: bytes | None
    poster_mime: str
    provider: str
    model: str
    prompt: str
    duration_seconds: int
    usage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class VideoProvider(Protocol):
    provider_name: str
    model: str

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResponse: ...


class GeminiVeoProvider:
    provider_name = "gemini-veo"

    def __init__(self, *, settings: Settings | None = None, model: str | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.model = model or DEFAULT_VEO_MODEL

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        import asyncio

        return await asyncio.to_thread(self._generate_sync, request)

    def _generate_sync(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        try:
            from google import genai
            from google.genai import types
        except Exception as exc:  # pragma: no cover - optional dependency
            raise VideoProviderUnavailable("google-genai SDK is not installed") from exc
        try:
            api_key = self.settings.require_google_api_key()
        except Exception as exc:
            raise VideoProviderUnavailable("GOOGLE_API_KEY is required for Veo video generation") from exc

        duration = request.clamped_duration()
        try:
            client = genai.Client(api_key=api_key)
            kwargs: dict[str, Any] = {
                "model": self.model,
                "prompt": request.prompt,
                "config": types.GenerateVideosConfig(
                    aspect_ratio=request.aspect_ratio,
                    duration_seconds=duration,
                    number_of_videos=1,
                ),
            }
            if request.reference_image is not None:
                image_bytes, mime = request.reference_image
                kwargs["image"] = types.Image(image_bytes=image_bytes, mime_type=mime)
            operation = client.models.generate_videos(**kwargs)
            deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
            while not operation.done:
                if time.monotonic() > deadline:
                    raise VideoProviderUnavailable("Veo operation timed out")
                time.sleep(_POLL_SECONDS)
                operation = client.operations.get(operation)
            videos = getattr(operation.response, "generated_videos", None) or []
            if not videos:
                raise VideoProviderUnavailable("Veo returned no videos")
            video = videos[0].video
            video_bytes = getattr(video, "video_bytes", None)
            if video_bytes is None:
                # Some SDK versions require an explicit download.
                video_bytes = client.files.download(file=video)
        except VideoProviderUnavailable:
            raise
        except Exception as exc:  # no secrets in message
            raise VideoProviderUnavailable(f"Veo generation failed: {exc.__class__.__name__}") from exc
        return VideoGenerationResponse(
            video_bytes=bytes(video_bytes),
            mime_type="video/mp4",
            poster_bytes=(request.reference_image[0] if request.reference_image else None),
            poster_mime=(request.reference_image[1] if request.reference_image else "image/png"),
            provider=self.provider_name,
            model=self.model,
            prompt=request.prompt,
            duration_seconds=duration,
            usage={"billable": True},
            metadata={"aspect_ratio": request.aspect_ratio},
        )
