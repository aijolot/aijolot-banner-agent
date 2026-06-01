"""Deterministic local image provider used by tests and safe demos."""

from __future__ import annotations

import hashlib
from io import BytesIO

from PIL import Image, ImageDraw

from app.services.gemini.image_provider import ImageGenerationRequest, ImageGenerationResponse


class FakeImageProvider:
    provider_name = "fake"
    model = "fake-nano-banana-v1"

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        digest = hashlib.sha256(
            f"{request.prompt}|{request.aspect_ratio}|{request.width}|{request.height}".encode("utf-8")
        ).digest()
        width, height = _dimensions(request)
        bg = tuple(32 + (value % 180) for value in digest[:3])
        accent = tuple(32 + (value % 180) for value in digest[3:6])

        image = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(image)
        # Deterministic abstract banner: safe, valid PNG, no text/logos/faces.
        step = max(4, width // 8)
        for index, x in enumerate(range(-step, width + step, step)):
            offset = digest[6 + index % (len(digest) - 6)] % max(1, height // 3)
            draw.polygon(
                [(x, height), (x + step * 2, height), (x + step, height // 2 - offset)],
                fill=accent if index % 2 == 0 else tuple(reversed(accent)),
            )
        draw.rectangle((0, 0, width - 1, height - 1), outline=tuple(255 - channel for channel in bg), width=1)

        output = BytesIO()
        image.save(output, format="PNG", optimize=True)
        image_bytes = output.getvalue()
        return ImageGenerationResponse(
            image_bytes=image_bytes,
            mime_type="image/png",
            provider=self.provider_name,
            model=self.model,
            prompt=request.prompt,
            aspect_ratio=request.aspect_ratio,
            usage={"estimated_cost_usd": 0.0, "billable": False},
            metadata={"deterministic_seed": hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()[:16]},
        )


def _dimensions(request: ImageGenerationRequest) -> tuple[int, int]:
    if request.width and request.height:
        return _clamp_dimension(request.width), _clamp_dimension(request.height)
    if request.aspect_ratio == "1:1":
        return 64, 64
    if request.aspect_ratio == "4:5":
        return 64, 80
    if request.aspect_ratio == "9:16":
        return 72, 128
    return 128, 72


def _clamp_dimension(value: int) -> int:
    return min(2048, max(1, int(value)))
