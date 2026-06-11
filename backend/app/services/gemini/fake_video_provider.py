"""Deterministic local video provider (C2) — tests and safe demos. Zero network.

Emits a minimal MP4-shaped byte stream (valid ftyp/mdat box structure, not a
playable encode) whose payload is derived from the prompt hash, plus a
deterministic poster PNG via the same drawing algorithm as FakeImageProvider —
so same prompt → same bytes on every run (demo-stable, resume-safe).
"""

from __future__ import annotations

import hashlib
import struct

from app.services.gemini.video_provider import VideoGenerationRequest, VideoGenerationResponse


def _box(box_type: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + box_type + payload


class FakeVideoProvider:
    provider_name = "fake"
    model = "fake-veo-v1"

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        digest = hashlib.sha256(f"{request.prompt}|{request.aspect_ratio}|{request.clamped_duration()}".encode()).digest()
        # MP4 box skeleton: ftyp + a deterministic mdat payload (~24KB).
        ftyp = _box(b"ftyp", b"isom" + struct.pack(">I", 512) + b"isomiso2avc1mp41")
        mdat = _box(b"mdat", digest * 768)
        video_bytes = ftyp + mdat

        if request.reference_image is not None:
            poster_bytes = request.reference_image[0]
        else:
            from app.services.gemini.fake_image_provider import FakeImageProvider
            from app.services.gemini.image_provider import ImageGenerationRequest

            poster = await FakeImageProvider().generate(
                ImageGenerationRequest(prompt=request.prompt, aspect_ratio=request.aspect_ratio)
            )
            poster_bytes = poster.image_bytes
        return VideoGenerationResponse(
            video_bytes=video_bytes,
            mime_type="video/mp4",
            poster_bytes=poster_bytes,
            poster_mime="image/png",
            provider=self.provider_name,
            model=self.model,
            prompt=request.prompt,
            duration_seconds=request.clamped_duration(),
            usage={"estimated_cost_usd": 0.0, "billable": False},
            metadata={"deterministic_seed": digest.hex()[:16], "not_playable": True},
        )
