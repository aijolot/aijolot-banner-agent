"""Image generation provider boundary.

The app imports this module without requiring Google credentials. The real Gemini
implementation is selected only by explicit configuration in the tool layer; tests
and local demo paths use :class:`FakeImageProvider` instead.
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.settings import MissingSettingsError, Settings


class ImageProviderUnavailable(RuntimeError):
    """Raised when a configured image provider cannot be used safely."""


@dataclass(frozen=True, slots=True)
class ImageGenerationRequest:
    prompt: str
    aspect_ratio: str = "16:9"
    width: int | None = None
    height: int | None = None
    user_id: str | None = None
    campaign_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    # Optional reference images (bytes, mime_type) fed alongside the prompt for
    # multimodal generation/editing — e.g. the real product photo so Nano Banana
    # composes the actual bottle into the hero rather than inventing one.
    reference_images: tuple[tuple[bytes, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ImageGenerationResponse:
    image_bytes: bytes
    mime_type: str
    provider: str
    model: str
    prompt: str
    aspect_ratio: str
    usage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def size_bytes(self) -> int:
        return len(self.image_bytes)


class ImageProvider(Protocol):
    provider_name: str
    model: str

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse: ...


class GeminiImageProvider:
    """Real Gemini image provider.

    This class never falls back silently. Callers must opt into it explicitly and
    provide credentials. Runtime errors are sanitized to avoid leaking secrets.
    """

    provider_name = "gemini"

    def __init__(self, *, settings: Settings | None = None, model: str | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.model = model or self.settings.gemini_model_image

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        return await asyncio.to_thread(self._generate_sync, request)

    def _generate_sync(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        try:
            api_key = self.settings.require_google_api_key()
        except MissingSettingsError as exc:
            raise ImageProviderUnavailable("Gemini image provider requires GOOGLE_API_KEY") from exc

        try:
            from google import genai
            from google.genai import types
        except Exception as exc:  # pragma: no cover - optional SDK/environment dependent
            raise ImageProviderUnavailable("Gemini SDK is not installed or could not be imported") from exc

        try:
            client = genai.Client(api_key=api_key)
            config = None
            try:
                config = types.GenerateContentConfig(response_modalities=["IMAGE"])
            except Exception:
                config = None
            # Multimodal contents: the text prompt plus any reference images (e.g. the
            # real product photo). Image parts come first so the model anchors on them.
            contents: Any = request.prompt
            if request.reference_images:
                parts: list[Any] = []
                for data, mime in request.reference_images:
                    if not data:
                        continue
                    try:
                        parts.append(types.Part.from_bytes(data=data, mime_type=mime or "image/jpeg"))
                    except Exception:  # pragma: no cover - SDK shape variance
                        continue
                parts.append(request.prompt)
                if len(parts) > 1:
                    contents = parts
            response = client.models.generate_content(model=self.model, contents=contents, config=config)
        except Exception as exc:  # pragma: no cover - external provider path
            raise ImageProviderUnavailable("Gemini image generation failed") from None

        image_bytes, mime_type = _extract_image(response)
        return ImageGenerationResponse(
            image_bytes=image_bytes,
            mime_type=mime_type,
            provider=self.provider_name,
            model=self.model,
            prompt=request.prompt,
            aspect_ratio=request.aspect_ratio,
            usage={"estimated_cost_usd": None},
            metadata={"real_provider": True},
        )


def _extract_image(response: Any) -> tuple[bytes, str]:
    """Extract inline image bytes from a google-genai response shape."""

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
            if inline is None:
                continue
            data = getattr(inline, "data", None)
            if data is None:
                continue
            mime_type = getattr(inline, "mime_type", None) or getattr(inline, "mimeType", None) or "image/png"
            if isinstance(data, str):
                try:
                    data = base64.b64decode(data, validate=True)
                except Exception:
                    raise ImageProviderUnavailable("Gemini response included invalid image bytes") from None
            if isinstance(data, bytes | bytearray):
                return bytes(data), str(mime_type)
    raise ImageProviderUnavailable("Gemini response did not include image bytes")
